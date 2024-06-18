#! /bin/bash

if ! command -v ansible &> /dev/null
then
	sudo apt install software-properties-common
	sudo add-apt-repository --yes --update ppa:ansible/ansible
	sudo apt update
	sudo apt install ansible
fi

ansible-galaxy install -r requirements.yml
