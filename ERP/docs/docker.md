# Docker Basics

Docker is a powerful platform that simplifies the process of building, shipping, and running applications using containerization. Here's an explanation of its core concepts:

## 1. Docker Images

A Docker image is a lightweight, standalone, executable package that includes everything needed to run a piece of software, including the code, a runtime, libraries, environment variables, and configuration files.

*   **Think of it as a blueprint or a template.** It's a read-only template that defines what goes into a container.
*   **Layered Structure:** Images are built up from a series of layers. Each instruction in a Dockerfile creates a new layer. This layering allows for efficient storage and distribution, as common layers can be shared between images.
*   **Immutability:** Once an image is built, it doesn't change. When you run an image, Docker adds a thin, writable layer on top, which is where all changes within the container occur.

**Example:** An image for a Python application might include:
*   An operating system base layer (e.g., Ubuntu or Alpine Linux)
*   Python runtime
*   Application code
*   Required Python libraries (from `requirements.txt`)

## 2. Docker Containers

A Docker container is a runnable instance of a Docker image. You can create, start, stop, move, or delete a container.

*   **Think of it as a running instance of your application.** It's a live, isolated environment based on an image.
*   **Isolation:** Containers are isolated from each other and from the host system. They have their own filesystem, network interfaces, and process space.
*   **Portability:** Because a container bundles everything needed to run, it can be moved and run consistently across different environments (your laptop, a test server, a production cloud).
*   **Ephemeral:** Containers are designed to be ephemeral. You can stop and remove a container, and all changes made within its writable layer are lost (unless you've explicitly saved data using volumes).

**Relationship between Images and Containers:**
You can think of a Docker image as a class and a Docker container as an instance of that class. You can create multiple containers from a single image.

## 3. Dockerfile

A Dockerfile is a text document that contains all the commands a user could call on the command line to assemble an image. It's essentially a script that Docker uses to build an image automatically.

*   **Instructions:** Each line in a Dockerfile is an instruction (e.g., `FROM`, `RUN`, `COPY`, `EXPOSE`, `CMD`).
*   **Build Process:** When you run `docker build` with a Dockerfile, Docker reads the instructions and executes them in order, creating a new layer for each instruction.

**Common Dockerfile Instructions:**
*   `FROM`: Specifies the base image (e.g., `FROM python:3.9-slim-buster`).
*   `WORKDIR`: Sets the working directory inside the container.
*   `COPY`: Copies files or directories from the host to the container.
*   `RUN`: Executes commands during the image build process (e.g., `RUN pip install -r requirements.txt`).
*   `EXPOSE`: Informs Docker that the container listens on the specified network ports at runtime.
*   `CMD`: Provides default commands for an executing container. This command is executed when a container is started from the image.
*   `ENTRYPOINT`: Configures a container that will run as an executable.

## 4. docker-compose.yml

`docker-compose.yml` is a YAML file that defines how to run multiple Docker containers as a single service. It's used for defining and running multi-container Docker applications.

*   **Orchestration for Development:** While Docker Swarm or Kubernetes are used for production orchestration, `docker-compose` is ideal for local development environments where you need to manage several interconnected services (e.g., a web application, a database, a caching service).
*   **Service Definition:** In `docker-compose.yml`, you define each service (container) that makes up your application, including:
    *   The Docker image to use (or a `build` context pointing to a Dockerfile).
    *   Port mappings.
    *   Volume mappings (for persistent data).
    *   Environment variables.
    *   Dependencies between services.
*   **Single Command Management:** With `docker-compose`, you can start, stop, and rebuild all services for your application with a single command (`docker-compose up`).

**Example Structure:**

```yaml
version: '3.8'
services:
  web:
    build: .
    ports:
      - "8000:8000"
    volumes:
      - .:/app
    depends_on:
      - db
  db:
    image: postgres:13
    environment:
      POSTGRES_DB: mydatabase
      POSTGRES_USER: user
      POSTGRES_PASSWORD: password
    volumes:
      - db_data:/var/lib/postgresql/data

volumes:
  db_data:
```

This `docker-compose.yml` defines two services: `web` (your application, built from the current directory's Dockerfile) and `db` (a PostgreSQL database). They are linked, and data for the database is persisted using a named volume.