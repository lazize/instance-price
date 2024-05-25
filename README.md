# Pricing File from Region

## Operating System Options

```shell
$ aws pricing get-attribute-values --service-code AmazonEC2 --attribute-name operatingSystem --region us-east-1 --query "AttributeValues[].[Value]" --output text | sort | uniq
Linux
NA
RHEL
Red Hat Enterprise Linux with HA
SUSE
Ubuntu Pro
Windows
```

## Generate pricing json file

```shell
REGION="sa-east-1"
OS="Linux"
aws --region us-east-1 pricing get-products --service-code AmazonEC2 --filters \
    "Type=TERM_MATCH,Field=capacitystatus,Value=Used" \
    "Type=TERM_MATCH,Field=marketoption,Value=OnDemand" \
    "Type=TERM_MATCH,Field=regionCode,Value=${REGION}" \
    "Type=TERM_MATCH,Field=operatingSystem,Value=${OS}" \
    "Type=TERM_MATCH,Field=servicecode,Value=AmazonEC2" \
    "Type=TERM_MATCH,Field=tenancy,Value=Shared" \
    "Type=TERM_MATCH,Field=operation,Value=RunInstances" \
    "Type=TERM_MATCH,Field=currentGeneration,Value=Yes" \
 | jq -r '.' > "price-list-${REGION}.json"
```

----

# Describe Instance Types from Region

```shell
REGION="sa-east-1"
aws --region "${REGION}" ec2 describe-instance-types > "instance-types-${REGION}.json"
```
