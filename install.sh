#! /bin/bash

if ! command -v ansible &> /dev/null
then
	apt install software-properties-common
	add-apt-repository --yes --update ppa:ansible/ansible
	apt update
	apt install ansible
fi

ansible-galaxy install -r requirements.yml
