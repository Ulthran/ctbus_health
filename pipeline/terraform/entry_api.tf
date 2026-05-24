data "archive_file" "entry_api" {
  type        = "zip"
  source_file = "${path.module}/../api/index.py"
  output_path = "${path.module}/build/entry_api.zip"
}

resource "aws_iam_role" "entry_api" {
  name = "ctbus-food-entry-api"
  assume_role_policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect    = "Allow"
      Principal = { Service = "lambda.amazonaws.com" }
      Action    = "sts:AssumeRole"
    }]
  })
}

resource "aws_iam_role_policy_attachment" "entry_api_logs" {
  role       = aws_iam_role.entry_api.name
  policy_arn = "arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole"
}

resource "aws_iam_role_policy" "entry_api" {
  role = aws_iam_role.entry_api.name
  policy = jsonencode({
    Version = "2012-10-17"
    Statement = [{
      Effect   = "Allow"
      Action   = ["sqs:SendMessage"]
      Resource = aws_sqs_queue.food_queue.arn
    }]
  })
}

resource "aws_lambda_function" "entry_api" {
  function_name    = "ctbus-food-entry-api"
  role             = aws_iam_role.entry_api.arn
  runtime          = "python3.13"
  handler          = "index.lambda_handler"
  filename         = data.archive_file.entry_api.output_path
  source_code_hash = data.archive_file.entry_api.output_base64sha256
  timeout          = 30
  memory_size      = 128

  environment {
    variables = {
      QUEUE_URL   = aws_sqs_queue.food_queue.url
      CORS_ORIGIN = "https://${var.domain_name}"
    }
  }
}

resource "aws_apigatewayv2_api" "entry" {
  name          = "ctbus-entry-api"
  protocol_type = "HTTP"
  cors_configuration {
    allow_origins = [
      "https://${var.domain_name}",
      "http://localhost:8081",
    ]
    allow_methods = ["POST", "OPTIONS"]
    allow_headers = ["Content-Type", "Authorization"]
    max_age       = 3600
  }
}

resource "aws_apigatewayv2_authorizer" "cognito" {
  api_id           = aws_apigatewayv2_api.entry.id
  authorizer_type  = "JWT"
  identity_sources = ["$request.header.Authorization"]
  name             = "cognito"

  jwt_configuration {
    audience = [aws_cognito_user_pool_client.frontend.id]
    issuer   = "https://cognito-idp.${var.aws_region}.amazonaws.com/${aws_cognito_user_pool.main.id}"
  }
}

resource "aws_apigatewayv2_integration" "entry_api" {
  api_id                 = aws_apigatewayv2_api.entry.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.entry_api.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "entry" {
  api_id             = aws_apigatewayv2_api.entry.id
  route_key          = "POST /entry"
  target             = "integrations/${aws_apigatewayv2_integration.entry_api.id}"
  authorization_type = "JWT"
  authorizer_id      = aws_apigatewayv2_authorizer.cognito.id
}

resource "aws_apigatewayv2_stage" "entry" {
  api_id      = aws_apigatewayv2_api.entry.id
  name        = "$default"
  auto_deploy = true
}

resource "aws_lambda_permission" "entry_api_apigw" {
  statement_id  = "AllowAPIGatewayInvoke"
  action        = "lambda:InvokeFunction"
  function_name = aws_lambda_function.entry_api.function_name
  principal     = "apigateway.amazonaws.com"
  source_arn    = "${aws_apigatewayv2_api.entry.execution_arn}/*/*"
}
