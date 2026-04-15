# Initial Terraform skeleton only.
# Networking, security, secrets, RDS, Lambda, and AppSync resources will be added next.

locals {
  tags = {
    Project = var.project_name
    ManagedBy = "terraform"
  }
}
