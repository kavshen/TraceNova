# Docker Notes

## Docker

Docker runs applications and required services in isolated containers.

It avoids installing services such as PostgreSQL and Redis directly on the computer.

## Image and container

- **Image:** reusable packaged template.
- **Container:** a running copy of an image.

Example:

```text
postgres:16-alpine → PostgreSQL image → running PostgreSQL container