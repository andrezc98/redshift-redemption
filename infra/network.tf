# The lab brings its own VPC: private subnets only, no NAT. The Data API needs no
# inbound path. Three AZs because Serverless workgroups want them.
#
# Enhanced VPC routing is on for every cluster (speaker's call, 2026-10-05), so
# COPY, UNLOAD and data lake queries must reach S3, Glue and Lake Formation from
# inside this VPC. "Create the following VPC endpoints [...] required for both the
# integrated data lake query engine and Amazon Redshift Spectrum: Amazon S3 gateway
# endpoint, AWS Glue interface endpoint, AWS Lake Formation interface endpoint"
# (https://docs.aws.amazon.com/redshift/latest/mgmt/spectrum-enhanced-vpc.html,
# read 2026-10-05). Service names checked with describe-vpc-endpoint-services in
# us-east-1 the same day.
data "aws_availability_zones" "up" {
  state = "available"
}

resource "aws_vpc" "lab" {
  cidr_block           = "10.42.0.0/16"
  enable_dns_hostnames = true # interface endpoints need private DNS to answer the public service names
  tags                 = { Name = "rr-lab" }
}

resource "aws_subnet" "private" {
  count             = 3
  vpc_id            = aws_vpc.lab.id
  cidr_block        = cidrsubnet(aws_vpc.lab.cidr_block, 4, count.index)
  availability_zone = data.aws_availability_zones.up.names[count.index]
  tags              = { Name = "rr-private-${count.index}" }
}

resource "aws_security_group" "redshift" {
  name        = "rr-redshift"
  description = "Redshift lab: no inbound, all outbound"
  vpc_id      = aws_vpc.lab.id

  egress {
    from_port   = 0
    to_port     = 0
    protocol    = "-1"
    cidr_blocks = ["0.0.0.0/0"]
  }
}

resource "aws_redshift_subnet_group" "lab" {
  name       = "rr-lab"
  subnet_ids = aws_subnet.private[*].id
}

# Gateway endpoint: free, and it also covers the public redshift-downloads bucket
# (same region). The subnets have no route table of their own, so they use the
# VPC's main one.
resource "aws_vpc_endpoint" "s3" {
  vpc_id            = aws_vpc.lab.id
  service_name      = "com.amazonaws.us-east-1.s3"
  vpc_endpoint_type = "Gateway"
  route_table_ids   = [aws_vpc.lab.main_route_table_id]
  tags              = { Name = "rr-s3" }
}

resource "aws_security_group" "endpoints" {
  name        = "rr-endpoints"
  description = "Interface endpoints: HTTPS from inside the lab VPC"
  vpc_id      = aws_vpc.lab.id

  ingress {
    from_port   = 443
    to_port     = 443
    protocol    = "tcp"
    cidr_blocks = [aws_vpc.lab.cidr_block]
  }
}

# s3tables is not on the docs list above; it is there because the lab writes
# Iceberg into an S3 table bucket and a missing route costs a lab hour, while the
# endpoint costs cents. ponytail: drop it if a run proves it unused.
resource "aws_vpc_endpoint" "interface" {
  for_each            = toset(["glue", "lakeformation", "s3tables"])
  vpc_id              = aws_vpc.lab.id
  service_name        = "com.amazonaws.us-east-1.${each.key}"
  vpc_endpoint_type   = "Interface"
  subnet_ids          = aws_subnet.private[*].id
  security_group_ids  = [aws_security_group.endpoints.id]
  private_dns_enabled = true
  tags                = { Name = "rr-${each.key}" }
}
