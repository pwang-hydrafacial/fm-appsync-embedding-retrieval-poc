output "appsync_url" {
  value = aws_appsync_graphql_api.main.uris["GRAPHQL"]
}

output "appsync_api_key" {
  value     = aws_appsync_api_key.main.key
  sensitive = true
}

output "rds_endpoint" {
  value = aws_db_instance.postgres.address
}

output "secret_arn" {
  value = aws_secretsmanager_secret.db.arn
}

output "lambda_function_name" {
  value = aws_lambda_function.retrieval.function_name
}
