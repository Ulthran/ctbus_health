resource "aws_apigatewayv2_api" "telegram" {
  name          = "ctbus-food-pipeline"
  protocol_type = "HTTP"
}

resource "aws_apigatewayv2_integration" "listener" {
  api_id                 = aws_apigatewayv2_api.telegram.id
  integration_type       = "AWS_PROXY"
  integration_uri        = aws_lambda_function.listener.invoke_arn
  payload_format_version = "2.0"
}

resource "aws_apigatewayv2_route" "telegram" {
  api_id    = aws_apigatewayv2_api.telegram.id
  route_key = "POST /telegram"
  target    = "integrations/${aws_apigatewayv2_integration.listener.id}"
}

resource "aws_apigatewayv2_stage" "default" {
  api_id      = aws_apigatewayv2_api.telegram.id
  name        = "$default"
  auto_deploy = true
}
