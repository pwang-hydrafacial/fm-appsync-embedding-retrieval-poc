locals {
  tags = {
    Project   = var.project_name
    ManagedBy = "terraform"
  }
  name = var.project_name
}

# ─── Password ─────────────────────────────────────────────────────────────────
resource "random_password" "db" {
  length  = 24
  special = false
}

# ─── VPC ──────────────────────────────────────────────────────────────────────
resource "aws_vpc" "main" {
  cidr_block           = "10.0.0.0/16"
  enable_dns_support   = true
  enable_dns_hostnames = true
  tags                 = merge(local.tags, { Name = "${local.name}-vpc" })
}

resource "aws_subnet" "private_a" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.1.0/24"
  availability_zone = "${var.aws_region}a"
  tags              = merge(local.tags, { Name = "${local.name}-private-a" })
}

resource "aws_subnet" "private_b" {
  vpc_id            = aws_vpc.main.id
  cidr_block        = "10.0.2.0/24"
  availability_zone = "${var.aws_region}b"
  tags              = merge(local.tags, { Name = "${local.name}-private-b" })
}

# ─── Security Groups ──────────────────────────────────────────────────────────
resource "aws_security_group" "lambda" {
  name        = "${local.name}-lambda"
  description = "Lambda egress"
  vpc_id      = aws_vpc.main.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "rds" {
  name        = "${local.name}-rds"
  description = "RDS ingress"
  vpc_id      = aws_vpc.main.id

  ingress {
    description     = "Postgres from Lambda"
    from_port       = 5432
    to_port         = 5432
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  # POC: allow seed script to connect from local machine
  ingress {
    description = "Postgres from anywhere for seed/admin"
    from_port   = 5432
    to_port     = 5432
    protocol    = "tcp"
    cidr_blocks = ["0.0.0.0/0"]
  }

  tags = local.tags
}

resource "aws_security_group" "endpoints" {
  name        = "${local.name}-endpoints"
  description = "VPC interface endpoints"
  vpc_id      = aws_vpc.main.id

  ingress {
    from_port       = 443
    to_port         = 443
    protocol        = "tcp"
    security_groups = [aws_security_group.lambda.id]
  }

  tags = local.tags
}

# ─── Internet Gateway (required for RDS publicly_accessible) ─────────────────
resource "aws_internet_gateway" "main" {
  vpc_id = aws_vpc.main.id
  tags   = merge(local.tags, { Name = "${local.name}-igw" })
}

resource "aws_route_table" "public" {
  vpc_id = aws_vpc.main.id

  route {
    cidr_block = "0.0.0.0/0"
    gateway_id = aws_internet_gateway.main.id
  }

  tags = merge(local.tags, { Name = "${local.name}-rt-public" })
}

resource "aws_route_table_association" "public_a" {
  subnet_id      = aws_subnet.private_a.id
  route_table_id = aws_route_table.public.id
}

resource "aws_route_table_association" "public_b" {
  subnet_id      = aws_subnet.private_b.id
  route_table_id = aws_route_table.public.id
}

# ─── VPC Endpoints (Lambda reaches AWS services without NAT) ──────────────────
resource "aws_vpc_endpoint" "secretsmanager" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.secretsmanager"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-sm-ep" })
}

resource "aws_vpc_endpoint" "bedrock_runtime" {
  vpc_id              = aws_vpc.main.id
  service_name        = "com.amazonaws.${var.aws_region}.bedrock-runtime"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = merge(local.tags, { Name = "${local.name}-bedrock-ep" })
}

# ─── Secrets Manager ──────────────────────────────────────────────────────────
resource "aws_secretsmanager_secret" "db" {
  name                    = "${local.name}/db"
  recovery_window_in_days = 0
  tags                    = local.tags
}

resource "aws_secretsmanager_secret_version" "db" {
  secret_id = aws_secretsmanager_secret.db.id
  secret_string = jsonencode({
    username = var.db_username
    password = random_password.db.result
    host     = aws_db_instance.postgres.address
    port     = 5432
    dbname   = var.db_name
  })
}

# ─── RDS ──────────────────────────────────────────────────────────────────────
resource "aws_db_subnet_group" "postgres" {
  name       = "${local.name}-db-subnet-group"
  subnet_ids = [aws_subnet.private_a.id, aws_subnet.private_b.id]
  tags       = local.tags
}

resource "aws_db_instance" "postgres" {
  identifier             = "${local.name}-db"
  engine                 = "postgres"
  engine_version         = "16.6"
  instance_class         = var.db_instance_class
  allocated_storage      = 20
  db_name                = var.db_name
  username               = var.db_username
  password               = random_password.db.result
  db_subnet_group_name   = aws_db_subnet_group.postgres.name
  vpc_security_group_ids = [aws_security_group.rds.id]
  publicly_accessible    = true # seed script connects from local
  skip_final_snapshot    = true
  multi_az               = false
  tags                   = local.tags
}

# ─── Lambda IAM ───────────────────────────────────────────────────────────────
resource "aws_iam_role" "lambda" {
  name = "${local.name}-lambda-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy_attachment" "lambda_vpc" {
  role       = aws_iam_role.lambda.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaVPCAccessExecutionRole"
}

resource "aws_iam_role_policy" "lambda" {
  name = "${local.name}-lambda-policy"
  role = aws_iam_role.lambda.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [
      {
        Effect   = "Allow"
        Action   = ["bedrock:InvokeModel"]
        Resource = "arn:aws:bedrock:${var.aws_region}::foundation-model/${var.bedrock_model_id}"
      },
      {
        Effect   = "Allow"
        Action   = ["secretsmanager:GetSecretValue"]
        Resource = aws_secretsmanager_secret.db.arn
      }
    ]
  })
}

# ─── Lambda Package ───────────────────────────────────────────────────────────
resource "aws_lambda_layer_version" "deps" {
  layer_name          = "${local.name}-deps"
  filename            = "${path.module}/../build/layer.zip"
  source_code_hash    = filebase64sha256("${path.module}/../build/layer.zip")
  compatible_runtimes = ["python3.12"]
}

data "archive_file" "lambda" {
  type        = "zip"
  source_dir  = "${path.module}/../app/lambda"
  output_path = "${path.module}/../build/lambda.zip"
}

resource "aws_lambda_function" "retrieval" {
  function_name    = "${local.name}-retrieval"
  role             = aws_iam_role.lambda.arn
  handler          = "handler.handler"
  runtime          = "python3.12"
  filename         = data.archive_file.lambda.output_path
  source_code_hash = data.archive_file.lambda.output_base64sha256
  timeout          = 30
  memory_size      = 256
  layers           = [aws_lambda_layer_version.deps.arn]

  vpc_config {
    subnet_ids         = [aws_subnet.private_a.id, aws_subnet.private_b.id]
    security_group_ids = [aws_security_group.lambda.id]
  }

  environment {
    variables = {
      SECRET_ARN       = aws_secretsmanager_secret.db.arn
      BEDROCK_MODEL_ID = var.bedrock_model_id
      EMBEDDING_DIM    = tostring(var.embedding_dim)
    }
  }

  depends_on = [aws_iam_role_policy_attachment.lambda_vpc]
  tags       = local.tags
}

# ─── AppSync ──────────────────────────────────────────────────────────────────
resource "aws_appsync_graphql_api" "main" {
  name                = local.name
  authentication_type = "API_KEY"
  schema              = file("${path.module}/../app/graphql/schema.graphql")
  tags                = local.tags
}

resource "aws_appsync_api_key" "main" {
  api_id  = aws_appsync_graphql_api.main.id
  expires = "2027-04-16T00:00:00Z"
}

resource "aws_iam_role" "appsync" {
  name = "${local.name}-appsync-role"

  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "appsync.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })

  tags = local.tags
}

resource "aws_iam_role_policy" "appsync" {
  name = "${local.name}-appsync-policy"
  role = aws_iam_role.appsync.id

  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["lambda:InvokeFunction"]
      Resource = aws_lambda_function.retrieval.arn
    }]
  })
}

resource "aws_appsync_datasource" "lambda" {
  api_id           = aws_appsync_graphql_api.main.id
  name             = "LambdaRetrieval"
  type             = "AWS_LAMBDA"
  service_role_arn = aws_iam_role.appsync.arn

  lambda_config {
    function_arn = aws_lambda_function.retrieval.arn
  }
}

resource "aws_appsync_resolver" "retrieve" {
  api_id      = aws_appsync_graphql_api.main.id
  type        = "Query"
  field       = "retrieve"
  data_source = aws_appsync_datasource.lambda.name

  request_template = <<-EOT
    {
      "version": "2018-05-29",
      "operation": "Invoke",
      "payload": {
        "arguments": $util.toJson($ctx.args)
      }
    }
  EOT

  response_template = "$util.toJson($ctx.result)"
}
