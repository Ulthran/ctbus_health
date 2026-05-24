data "aws_route53_zone" "charliebushman" {
  name         = "charliebushman.com"
  private_zone = false
}

locals {
  # *.charliebushman.com cert — not returned by ListCertificates, referenced by ARN directly
  acm_cert_arn = "arn:aws:acm:us-east-1:832242454463:certificate/f7e30d65-53f8-4852-834a-32d29ca145eb"
}

resource "aws_cloudfront_origin_access_control" "frontend" {
  name                              = "ctbus-health-frontend"
  origin_access_control_origin_type = "s3"
  signing_behavior                  = "always"
  signing_protocol                  = "sigv4"
}

resource "aws_cloudfront_distribution" "frontend" {
  enabled             = true
  is_ipv6_enabled     = true
  default_root_object = "index.html"
  aliases             = [var.domain_name]

  origin {
    domain_name              = aws_s3_bucket.health_data.bucket_regional_domain_name
    origin_id                = "s3-health-data"
    origin_access_control_id = aws_cloudfront_origin_access_control.frontend.id
  }

  # Default: serve frontend files without auth
  default_cache_behavior {
    target_origin_id       = "s3-health-data"
    viewer_protocol_policy = "redirect-to-https"
    allowed_methods        = ["GET", "HEAD", "OPTIONS"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 86400
  }

  # Diet data: JWT required, no caching
  ordered_cache_behavior {
    path_pattern           = "/diet/*"
    target_origin_id       = "s3-health-data"
    viewer_protocol_policy = "https-only"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      headers      = ["Authorization"]
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    lambda_function_association {
      event_type   = "viewer-request"
      lambda_arn   = aws_lambda_function.auth_edge.qualified_arn
      include_body = false
    }
  }

  # Photos: JWT required, no caching
  ordered_cache_behavior {
    path_pattern           = "/photos/*"
    target_origin_id       = "s3-health-data"
    viewer_protocol_policy = "https-only"
    allowed_methods        = ["GET", "HEAD"]
    cached_methods         = ["GET", "HEAD"]

    forwarded_values {
      query_string = false
      headers      = ["Authorization"]
      cookies { forward = "none" }
    }

    min_ttl     = 0
    default_ttl = 0
    max_ttl     = 0

    lambda_function_association {
      event_type   = "viewer-request"
      lambda_arn   = aws_lambda_function.auth_edge.qualified_arn
      include_body = false
    }
  }

  custom_error_response {
    error_code            = 403
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  custom_error_response {
    error_code            = 404
    response_code         = 200
    response_page_path    = "/index.html"
    error_caching_min_ttl = 0
  }

  restrictions {
    geo_restriction { restriction_type = "none" }
  }

  viewer_certificate {
    acm_certificate_arn      = local.acm_cert_arn
    ssl_support_method       = "sni-only"
    minimum_protocol_version = "TLSv1.2_2021"
  }
}

resource "aws_route53_record" "frontend" {
  zone_id = data.aws_route53_zone.charliebushman.zone_id
  name    = var.domain_name
  type    = "A"

  alias {
    name                   = aws_cloudfront_distribution.frontend.domain_name
    zone_id                = aws_cloudfront_distribution.frontend.hosted_zone_id
    evaluate_target_health = false
  }
}
