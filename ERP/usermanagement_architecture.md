# User Management Module Architecture

The `usermanagement` module is responsible for handling user authentication, authorization, and other user-related functionalities. It is built on top of Django's built-in authentication system but extends it with a comprehensive multi-tenant, role-based access control (RBAC) system to meet the specific needs of the application.

## Core Components

- **`models.py`**: Defines the data layer for the user management module. The data model is well-structured and provides a solid foundation for a multi-tenant application. Key models include:
    - **`Organization`**: The top-level entity for multi-tenancy. Each user and most other data in the system is associated with an organization.
    - **`CustomUser`**: A custom user model that extends Django's `AbstractUser`. It includes additional fields for managing user profiles, security, and multi-tenancy.
    - **`UserOrganization`**: A through model that links users to organizations, allowing a user to belong to multiple organizations with different roles.
    - **RBAC Models**:
        - **`Module` and `Entity`**: These models define a hierarchical structure for organizing permissions, making the system scalable and easy to manage.
        - **`Permission`**: Defines the specific actions that a user can perform on an entity (e.g., `view`, `add`, `change`, `delete`).
        - **`Role`**: A collection of permissions that can be assigned to users.
        - **`UserRole`**: A through model that assigns roles to users within a specific organization.
        - **`UserPermission`**: Allows for granting or revoking specific permissions to a user, overriding the permissions granted by their roles.
    - **`LoginLog`**: Tracks user login attempts, providing a valuable audit trail for security and monitoring.

- **`views.py`**: The views are a mix of function-based and class-based views, following standard Django patterns.
    - **Authentication Views**: The module includes a `custom_login` view and a `logout_view` to handle user authentication.
    - **CRUD Views**: The module provides a set of CRUD (Create, Read, Update, Delete) views for managing users, roles, permissions, and other user-related data. These are implemented using a combination of function-based views for simple operations and class-based views (e.g., `ListView`, `CreateView`, `UpdateView`) for more complex scenarios.
    - **Organization Switching**: The `select_organization` view allows users to switch between the organizations they belong to, which is a key feature for multi-tenancy.

- **`forms.py`**: The forms are standard Django `ModelForm` implementations, with each form corresponding to a specific model.
    - **`CustomUserCreationForm`**: A custom form for creating new users.
    - **RBAC Forms**: The module includes forms for managing roles, permissions, and user-role assignments.
    - **Login Form**: The `DasonLoginForm` is a custom authentication form that is styled with Bootstrap.

- **`urls.py`**: Defines the URL patterns for the user management module.
- **`admin.py`**: Registers the custom user model and other related models with the Django admin interface.

## Authentication and Authorization

- **`authentication.py`**: Implements custom authentication backends, allowing for different authentication strategies.
- **`middleware.py`**: Contains custom middleware for handling user sessions and authentication.
- **`signals.py`**: Defines signals that are triggered on user-related events, such as user login or registration.

## Permissions and Roles

The module includes a robust role-based access control (RBAC) system:

- **`management/commands/`**: This directory contains a suite of custom Django management commands that are essential for the initial setup, configuration, and ongoing maintenance of the application. These commands automate critical tasks that would otherwise be tedious and error-prone to perform manually.
    - **Purpose**: The primary purpose of these commands is to bootstrap the application with the necessary data and to keep the permissions system in sync. They are designed to be run from the command line (e.g., `python manage.py <command_name>`) and are typically used during deployment or as part of a CI/CD pipeline.
    - **Key Commands**:
        - **`seed_database`**: Wraps `scripts/seed_database.py` to create the superuser, tenant, organizations, roles, permissions, accounting structures, demo vouchers, inventory, LPG, and service-management seed data. It is idempotent and now serves as the single entry point for setting up a new instance.
        - **`generate_permissions` and `sync_custom_permissions`**: These commands work together to manage the permissions system. `generate_permissions` introspects the application's models to create a set of `Permission` objects based on the available actions (e.g., `view`, `add`, `change`, `delete`). `sync_custom_permissions` then synchronizes these custom `Permission` objects with Django's built-in `auth.Permission` model, making them available to the rest of the Django ecosystem.
- **`templatetags/permission_tags.py`**: Provides custom template tags for checking user permissions directly in the templates.

## Architectural Diagram

```mermaid
graph TD
    subgraph User Interface
        A[Templates]
    end

    subgraph Application Layer
        B[Views]
        C[Forms]
        D[URLs]
    end

    subgraph Security
        E[Authentication]
        F[Middleware]
        G[Permissions]
    end

    subgraph Data Layer
        H[Models]
        I[Database]
    end

    subgraph "Key Models"
        CustomUser -- "has many" --> UserOrganization
        Organization -- "has many" --> UserOrganization
        Role -- "has many" --> UserRole
        CustomUser -- "has many" --> UserRole
        Role -- "has many" --> Permission
    end

    A --> B
    C --> B
    D --> B
    B --> E
    E --> H
    F --> B
    G --> B
    H --> I
    H -.-> CustomUser