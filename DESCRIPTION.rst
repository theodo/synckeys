SSHKEY
======

SSHKEY is a simple project to manage the deployment of ssh keys of multiple people on multiple servers.

The usage is quite simple:
 * list all the ssh keys in keys.yml
 * list all the projects in acl.yml and link them to the corresponding authorized keys
 * run synckeys.py: all servers you are allowed to access will be updated with the corresponding keys

The principles behind sshkeys:
------------------------------


***Make things as visible as possible to make them more secure***

This is why the list of projects is a straightforward yaml list: much more readable than a puppet provisioning, you can expect more people to use it and to be aware of who has access to what.

***Make it easy to adopt to make it the central access control repository***

Anyone can easily add another key to a server they already have access to.
