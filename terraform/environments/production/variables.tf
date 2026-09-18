variable "aws_account_id" {
  type    = string
  default = "908027381953"
}

variable "image_tag" {
  description = "Tag of the openforge_catalog/api image to run (the git sha the Production workflow pushed)"
  type        = string
}
