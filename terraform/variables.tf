variable "aws_region" {
  type        = string
  description = "AWS region"
  default     = "us-east-1"
}

variable "project_name" {
  type        = string
  description = "Project name prefix"
  default     = "fm-appsync-embedding-retrieval-poc"
}

variable "db_instance_class" {
  type        = string
  description = "RDS instance class"
  default     = "db.t4g.micro"
}

variable "db_name" {
  type        = string
  description = "Initial database name"
  default     = "embeddingdb"
}

variable "db_username" {
  type        = string
  description = "Database admin username"
  default     = "appadmin"
}
