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

### launch ec2 instance ###
response = ec2.create_instances(ImageId=image_id,
                     InstanceType=instance_type,
                     MinCount=1,
                     MaxCount=1,
                     Placement=
                       {
     'AvailabilityZone': av_zone
                       },
                     SecurityGroups=['web sg'],
                     KeyName=key_pair_name,
                     )
instance_id = response[0].instance_id
instance = ec2.Instance(instance_id)
instance.wait_until_running()
ec2_client.attach_volume(
    VolumeId=volume_id,
    InstanceId=instance_id,
    Device='/dev/xvdl'
)
### get a list of running instances with additional options ###
for instance in ec2.instances.filter(Filters=[{'Name': 'instance-state-name', 'Values': ['running']}]):
   print(instance.id, instance.instance_type, instance.key_name, instance.private_ip_address, instance.public_ip_address)
#TODO should add the identification of my own instance between the already running ones

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
