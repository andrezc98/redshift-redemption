# The sandbox has no default VPC in us-east-1 (checked 2026-09-24), so the lab brings
# its own. Private subnets only and no NAT: the Data API needs no inbound path, and
# with enhanced VPC routing off (the default) COPY/Spectrum reach S3 over AWS's
# network, not through the VPC. Three AZs because Serverless workgroups want them.
data "aws_availability_zones" "up" {
  state = "available"
}

resource "aws_vpc" "lab" {
  cidr_block = "10.42.0.0/16"
  tags       = { Name = "rr-lab" }
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
