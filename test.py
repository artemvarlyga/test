#!/usr/bin/env python
import os
import sys
import time
import json
import boto3
from botocore.exceptions import ClientError
import paramiko

my_region = "us-east-1"
av_zone = my_region + "a"
vpc_id = "vpc-25517a5d"
security_group_name = "web sg"
instance_type = "t2.micro"
key_pair_name = "artemvarlyha"
image_id = "ami-b70554c8"
ssh_key_path = "/home/dda/.ssh/"+ key_pair_name +".pem"
k = paramiko.RSAKey.from_private_key_file(ssh_key_path)
c = paramiko.client.SSHClient()


def wait_for_ssh_to_be_ready (timeout, retry_interval):
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    retry_interval = float(retry_interval)
    timeout = int(timeout)
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        time.sleep(retry_interval)
        try:
            c.connect(hostname = instance.public_ip_address, username = "ec2-user", pkey = k)
        except paramiko.ssh_exception.SSHException as e:
            ### socket is open, but not SSH service responded ###
            if e.message == 'Error reading SSH protocol banner':
                print(e)
                continue
            print('SSH is available!')
            break
        except paramiko.ssh_exception.NoValidConnectionsError as e:
            print('SSH is not ready...')
            continue


ec2 = boto3.resource('ec2', region_name = my_region)
ec2_client = boto3.client('ec2',region_name = my_region)


### create security group ###
try:
    sec_group = ec2.create_security_group(
        GroupName=security_group_name,
        Description='web sec group',
        VpcId=vpc_id
    )

    sec_group.authorize_ingress(
       CidrIp='0.0.0.0/0',
       IpProtocol='tcp',
       FromPort=80,
       ToPort=80
    )
    sec_group.authorize_ingress(
       CidrIp='0.0.0.0/0',
       IpProtocol='tcp',
       FromPort=22,
       ToPort=22
    )
except ClientError as e:
   if e.response['Error']['Code'] == 'InvalidGroup.Duplicate':
      pass

### create volume ###
response = ec2_client.describe_volumes(
    Filters=[
        {
            'Name': 'tag:Name',
            'Values': [
                'web_vol'
            ]
        },
        {
            'Name': 'status',
            'Values': [
                'available'
            ]
        },
        {
            'Name': 'volume-type',
            'Values': [
                'standard'
            ]
        },
   ]
)
try:
  volume_id  =  response['Volumes'][0]['VolumeId']
except IndexError:
  volume_id = "0"
  pass

if volume_id == "0":

  volume = ec2.create_volume(
     Size=1,
     VolumeType='standard',
     AvailabilityZone=av_zone,
     TagSpecifications=[
          {
             'ResourceType': 'volume',
             'Tags': [
                 {
                     'Key': 'Name',
                     'Value': 'web_vol'
                 }
              ]
         }
     ]
  )
  volume_id = volume.id
print("ebs volume %s is ready for your instance" % volume_id)

### check if instance is already running ###
response = ec2_client.describe_instances(
    Filters=[
        {
            'Name': 'tag:Name',
            'Values': [
                'web_srv'
            ]
        },
        {
            'Name': 'instance-type',
            'Values': [
                instance_type
            ]
        },
        {
            'Name': 'instance-state-name',
            'Values': [
                'running'
            ]
        }
    ]
)
try:
  instance_id  =  response['Reservations'][0]['Instances'][0]['InstanceId']
except IndexError:
  instance_id = "0"
  pass

if instance_id == "0": ### then instance is absent and it has to be created

  response = ec2.create_instances(ImageId="%s" % image_id,
                       InstanceType="%s" % instance_type,
                       MinCount=1, MaxCount=1,
                       Placement=
                         {
                          'AvailabilityZone': 'eu-central-1a'
                         },
                       SecurityGroups=['web sg'],
                       KeyName="%s" % key_pair_name,
                       )
  instance_id = response[0].instance_id
  instance = ec2.Instance(instance_id)
  instance.wait_until_running()
  ec2_client.attach_volume(
      VolumeId="%s" % volume_id,
      InstanceId="%s" % instance_id,
      Device='/dev/xvdl'
  )
### assign tags to instance ###
  ec2.create_tags(
      Resources=[
        instance_id
      ],
      Tags=[
        {
          'Key': 'Name',
          'Value': 'web_srv'
        }
      ]
  )
  print("%s has been created" % instance_id)
else:
  print("Instance web_srv seems is alredy running in your AWS account")

### retrieve dns and public IP from web_srv instanse ###

response = ec2_client.describe_instances(
    Filters=[
        {
            'Name': 'instance-id',
            'Values': [
                instance_id
            ]
        }
    ]
)

dns = response['Reservations'][0]['Instances'][0]['PublicDnsName']
public_ip = response['Reservations'][0]['Instances'][0]['PublicIpAddress']



### get a list of running instances with additional options ###
for instance in ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
   print(instance.id, instance.instance_type, instance.key_name, instance.private_ip_address, instance.public_ip_address)

###  connect to , format the disk, mount it and perform git installation and repo clone ###
wait_for_ssh_to_be_ready('20', '3')
print ("connected")
commands = [ "echo '/dev/xvdl /my_volume    ext4 defaults 0  2' | sudo tee /etc/fstab",
             "sudo mkfs.ext4 /dev/xvdl",
             "sudo mkdir /my_volume",
             "sudo mount -a",
             "sudo yum update -y",
             "sudo yum -y install git",
             "sudo mkdir /my_volume/my_git"
             "sudo git clone https://github.com/artemvarlyga/test.git /my_volume/my_git",
             "sudo python  /my_volume/my_git/test.py --run_httpd",
          ]
for command in commands:
	print "Executing {}".format( command )
	stdin , stdout, stderr = c.exec_command(command)
	print stdout.read()
	print( "Errors")
	print stderr.read()
c.close()
