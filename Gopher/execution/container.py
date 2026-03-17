import docker
import logging
import os
import tarfile
import io
import time
from typing import Optional, Tuple, Dict, List
from contextlib import contextmanager
from docker.errors import DockerException, APIError

logger = logging.getLogger(__name__)

class ContainerExecutionError(Exception):
    """Raised when a container operation fails."""
    pass

class DockerContainerManager:

    def __init__(self,
                 image_name: str,
                 timeout: int = 600,
                 mem_limit: str = "4g",
                 nano_cpus: int = 2000000000):

        self.image_name = image_name
        self.timeout = timeout
        self.host_config = {
            "mem_limit": mem_limit,
            "nano_cpus": nano_cpus,
            "auto_remove": False
        }

        try:
            self.client = docker.from_env()
            self.client.ping()
        except DockerException as e:
            logger.critical("Failed to connect to Docker daemon. Is it running?")
            raise ContainerExecutionError("Docker daemon unreachable") from e

    @contextmanager
    def provision_container(self,
                            volumes: Optional[Dict[str, Dict]] = None,
                            environment: Optional[Dict] = None,
                            working_dir: str = "/workspace"):

        container = None
        try:
            logger.info(f"Starting container from image: {self.image_name}")
            container = self.client.containers.run(
                self.image_name,
                command="tail -f /dev/null",  # Keep container alive
                detach=True,
                volumes=volumes,
                environment=environment,
                working_dir=working_dir,
                **self.host_config
            )

            while container.status != 'running':
                container.reload()
                time.sleep(0.1)

            yield container

        except APIError as e:
            logger.error(f"Docker API error during provisioning: {e}")
            raise ContainerExecutionError(f"Failed to start container: {e}")
        finally:
            if container:
                logger.info(f"Stopping and removing container {container.short_id}...")
                try:
                    container.stop(timeout=1)
                    container.remove(force=True)
                except Exception as e:
                    logger.warning(f"Error during container cleanup: {e}")

    def exec_command(self,
                     container,
                     cmd: str,
                     workdir: Optional[str] = None,
                     timeout: Optional[int] = None) -> Tuple[int, str, str]:

        timeout = timeout or self.timeout
        logger.debug(f"Exec in {container.short_id}: {cmd}")
        wrapped_cmd = ["/bin/sh", "-c", cmd]
        try:

            exec_id = self.client.api.exec_create(
                container.id,
                wrapped_cmd,
                workdir=workdir,
                stdout=True,
                stderr=True
            )

            stream = self.client.api.exec_start(exec_id, detach=False)

            exit_code = self.client.api.exec_inspect(exec_id)['ExitCode']

            result = container.exec_run(
                wrapped_cmd,
                workdir=workdir,
                demux=True
            )

            stdout_bytes, stderr_bytes = result.output
            exit_code = result.exit_code

            stdout = stdout_bytes.decode('utf-8', errors='replace') if stdout_bytes else ""
            stderr = stderr_bytes.decode('utf-8', errors='replace') if stderr_bytes else ""

            return exit_code, stdout, stderr

        except Exception as e:
            logger.error(f"Command execution failed: {e}")
            return -1, "", str(e)

    def write_file(self, container, content: str, filepath: str):

        tar_stream = io.BytesIO()
        file_data = content.encode('utf-8')
        info = tarfile.TarInfo(name=os.path.basename(filepath))
        info.size = len(file_data)
        info.mtime = time.time()

        with tarfile.open(fileobj=tar_stream, mode='w') as tar:
            tar.addfile(info, io.BytesIO(file_data))

        tar_stream.seek(0)

        dir_path = os.path.dirname(filepath)

        try:
            container.exec_run(f"mkdir -p {dir_path}")

            container.put_archive(
                path=dir_path,
                data=tar_stream
            )
            logger.debug(f"Wrote file to container: {filepath}")
        except Exception as e:
            logger.error(f"Failed to write file {filepath}: {e}")
            raise ContainerExecutionError(f"File write failed: {e}")

    def read_file(self, container, filepath: str) -> str:

        try:
            bits, stat = container.get_archive(filepath)

            file_obj = io.BytesIO()
            for chunk in bits:
                file_obj.write(chunk)
            file_obj.seek(0)

            with tarfile.open(fileobj=file_obj, mode='r') as tar:
                member = tar.next()
                f = tar.extractfile(member)
                if f:
                    return f.read().decode('utf-8', errors='replace')
                return ""

        except docker.errors.NotFound:
            logger.error(f"File not found in container: {filepath}")
            raise FileNotFoundError(f"{filepath} not found inside container")
        except Exception as e:
            logger.error(f"Failed to read file {filepath}: {e}")
            raise ContainerExecutionError(f"File read failed: {e}")

    def ensure_image(self):
        try:
            self.client.images.get(self.image_name)
        except docker.errors.ImageNotFound:
            logger.info(f"Image {self.image_name} not found. Pulling...")
            self.client.images.pull(self.image_name)