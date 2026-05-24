locals {
  auth_edge_js = templatefile("${path.module}/../lambda_edge/auth.js.tpl", {
    issuer    = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
    jwks_url  = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}/.well-known/jwks.json"
    client_id = aws_cognito_user_pool_client.frontend.id
  })
}

data "archive_file" "auth_edge" {
  type = "zip"
  source {
    content  = local.auth_edge_js
    filename = "index.js"
  }
  output_path = "${path.module}/build/auth_edge.zip"
}

resource "aws_iam_role" "auth_edge" {
  name = "ctbus-food-auth-edge"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect = "Allow"
      Principal = {
        Service = ["lambda.amazonaws.com", "edgelambda.amazonaws.com"]
      }
      Action = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "auth_edge_logs" {
  role       = aws_iam_role.auth_edge.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_lambda_function" "auth_edge" {
  function_name    = "ctbus-food-auth-edge"
  role             = aws_iam_role.auth_edge.arn
  runtime          = "nodejs20.x"
  handler          = "index.handler"
  filename         = data.archive_file.auth_edge.output_path
  source_code_hash = data.archive_file.auth_edge.output_base64sha256
  publish          = true
  timeout          = 5
  memory_size      = 128
}
