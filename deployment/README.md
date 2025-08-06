# Deployment Guide

This directory contains the deployment configurations for the Selenium Grid on Kubernetes using Helm.

⚠️ Not meant to be used directly. Use `uvx mcp-selenium-grid helm deploy --help` instead. ⚠️

## Directory Structure

```txt
deployment/
└── helm/
    └── selenium-grid/
        ├── Chart.yaml          # Helm chart metadata
        ├── values.yaml         # Default configuration values
        └── templates/          # Kubernetes resource templates
            ├── namespace.yaml  # Namespace and resource quotas
            ├── rbac.yaml      # Service account and RBAC
            ├── network-policy.yaml  # Network isolation
            └── _helpers.tpl    # Template helpers
```

## Prerequisites

- [kubectl](https://kubernetes.io/docs/tasks/tools/)
- [Helm](https://helm.sh/docs/intro/install/)
- [K3s](https://k3s.io/) or any other Kubernetes distribution

## Installation

1. **Install the Helm chart**:

    ```bash
    # Install with default values
    helm install selenium-grid helm/selenium-grid

    # Install with custom values
    helm install selenium-grid helm/selenium-grid \
    --set namespace=my-namespace \
    --set serviceAccount.name=my-sa
    ```

2. **Verify the installation**:

    ```bash
    # Check the namespace
    kubectl get namespace selenium-grid

    # Check the service account
    kubectl get serviceaccount -n selenium-grid

    # Check the RBAC configuration
    kubectl get role,rolebinding -n selenium-grid
    ```

## Configuration

The chart can be configured through `values.yaml` or by passing values during installation:

```yaml
# Namespace configuration
namespace: selenium-grid

# Service Account configuration
serviceAccount:
  name: selenium-grid-sa
  create: true

# RBAC configuration
rbac:
  create: true
  role:
    name: selenium-grid-role
  roleBinding:
    name: selenium-grid-rolebinding

# Resource quotas
resources:
  limits:
    cpu: "2"
    memory: "2Gi"
  requests:
    cpu: "1"
    memory: "1Gi"
```

## Management

1. **Upgrade the chart**:

    ```bash
    helm upgrade selenium-grid helm/selenium-grid
    ```

2. **Uninstall the chart**:

    ```bash
    helm uninstall selenium-grid
    ```

3. **List releases**:

    ```bash
    helm list
    ```

## Security

The deployment includes several security features:

1. **Namespace Isolation**:
   - Dedicated namespace for Selenium Grid
   - Network policies for pod isolation
   - Resource quotas to prevent resource exhaustion

2. **RBAC**:
   - Service account with least privilege
   - Role-based access control
   - Specific permissions for required resources

3. **Resource Management**:
   - CPU and memory limits
   - Pod count restrictions
   - Resource requests for scheduling

## Troubleshooting

1. **Check pod status**:

    ```bash
    kubectl get pods -n selenium-grid
    ```

2. **View pod logs**:

    ```bash
    kubectl logs -n selenium-grid <pod-name>
    ```

3. **Describe resources**:

    ```bash
    kubectl describe namespace selenium-grid
    kubectl describe serviceaccount selenium-grid-sa -n selenium-grid
    ```

## Contributing

When adding new features or modifying the deployment:

1. Update the `values.yaml` with new configuration options
2. Add new templates in the `templates/` directory
3. Update this README with any new features or changes
4. Test the changes in a development environment first
