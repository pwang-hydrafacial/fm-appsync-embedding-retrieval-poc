variable "aws_region" {
  type    = string
  default = "us-east-1"
}

variable "project_name" {
  type    = string
  default = "fm-appsync-embedding-retrieval-poc"
}

variable "db_instance_class" {
  type    = string
  default = "db.t4g.micro"
}

variable "db_name" {
  type    = string
  default = "embeddingdb"
}

variable "db_username" {
  type    = string
  default = "appadmin"
}

variable "bedrock_model_id" {
  type    = string
  default = "amazon.titan-embed-text-v2:0"
}

variable "embedding_dim" {
  type    = number
  default = 1024
}
