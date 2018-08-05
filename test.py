# !/usr/bin/env python
import os
import sys
import time
import json
import argparse
import BaseHTTPServer
from SimpleHTTPServer import SimpleHTTPRequestHandler

my_region = "us-east-1"
av_zone = my_region + "a"
vpc_id = "vpc-25517a5d"
security_group_name = "web sg"
instance_type = "t2.micro"
key_pair_name = "artemvarlyha"
image_id = "ami-b70554c8"
ssh_key_path = "/home/dda/.ssh/" + key_pair_name + ".pem"

key = "YWRtaW46MTE2MTg="

class AuthHandler(SimpleHTTPRequestHandler):
    ''' Main class to present webpages and authentication. '''
    def do_HEAD(self):
        print "send header"
        self.send_response(200)
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_AUTHHEAD(self):
        print "send header"
        self.send_response(401)
        self.send_header('WWW-Authenticate', 'Basic realm=\"Test\"')
        self.send_header('Content-type', 'text/html')
        self.end_headers()

    def do_GET(self):
        global key
        ''' Present frontpage with user authentication. '''
        if self.headers.getheader('Authorization') == None:
            self.do_AUTHHEAD()
            self.wfile.write('no auth header received')
            pass
        elif self.headers.getheader('Authorization') == 'Basic '+key:
            SimpleHTTPRequestHandler.do_GET(self)
            pass
        else:
            self.do_AUTHHEAD()
            self.wfile.write(self.headers.getheader('Authorization'))
            self.wfile.write('not authenticated')
            pass

def test(HandlerClass = AuthHandler,
         ServerClass = BaseHTTPServer.HTTPServer, host='', port=80):
    server_address = (host, port)
    httpd = ServerClass(server_address, HandlerClass)
    httpd.serve_forever()


def wait_for_ssh_to_be_ready(timeout, retry_interval):
    c.set_missing_host_key_policy(paramiko.AutoAddPolicy())
    retry_interval = float(retry_interval)
    timeout = int(timeout)
    timeout_start = time.time()
    while time.time() < timeout_start + timeout:
        time.sleep(retry_interval)
        try:
            c.connect(hostname=instance.public_ip_address, username="ec2-user", pkey=k)
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


parser = argparse.ArgumentParser()
parser.add_argument("-r", help="runserver", action='store_true')
args = parser.parse_args()

if not len(sys.argv) > 1:
    import boto3
    import paramiko
    from botocore.exceptions import ClientError

    k = paramiko.RSAKey.from_private_key_file(ssh_key_path)
    c = paramiko.client.SSHClient()
    ec2 = boto3.resource('ec2', region_name=my_region)
    ec2_client = boto3.client('ec2', region_name=my_region)

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
        volume_id = response['Volumes'][0]['VolumeId']
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
        instance_id = response['Reservations'][0]['Instances'][0]['InstanceId']
    except IndexError:
        instance_id = "0"
        pass

    if instance_id == "0":  ### then instance is absent and it has to be created

        response = ec2.create_instances(ImageId=image_id,
                                        InstanceType=instance_type,
                                        MinCount=1, MaxCount=1,
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
        ###  connect to , format the disk, mount it and perform git installation and repo clone ###
        wait_for_ssh_to_be_ready('20', '3')
        print ("connected")
        commands = ["echo '/dev/xvdl /my_volume    ext4 defaults 0  2' | sudo tee /etc/fstab",
                    "sudo mkfs.ext4 /dev/xvdl",
                    "sudo mkdir /my_volume",
                    "sudo mount -a",
                    "sudo yum update -y",
                    "sudo yum -y install git",
                    "sudo mkdir /my_volume/my_git",
                    "sudo git clone https://github.com/artemvarlyga/test.git /my_volume/my_git",
                    '''sudo sh -c  "echo '* * * * * /bin/bash /my_volume/my_git/sss.sh > /my_volume/my_git/index.html' > /var/spool/cron/root"''',
                    '''sudo -- sh -c "cd /my_volume/my_git/; python test.py -r  </dev/null &>/dev/null &"'''
                    ]
        for command in commands:
            print "Executing {}".format(command)
            stdin, stdout, stderr = c.exec_command(command)
            print stdout.read()
            print("Errors")
            print stderr.read()
        c.close()
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
        print("http://%s/index.html" % instance.public_ip_address)

else:
    if args.r:
        test()
