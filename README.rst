========
synckeys
========

synckeys is a simple project to manage the deployment of ssh keys of multiple people on multiple servers.

The usage is quite simple:
 * list all the ssh keys you want to manage in keys.yml
 * list all the projects in acl.yml and link them to the corresponding authorized keys
 * just run synckeys: all servers you are allowed to access will be synced with the correct keys

The principles behind synckeys
==============================


What you see is what you get is more secure
-------------------------------------------

The list of projects is a straightforward yaml list:
 * much more readable than a shell script or a fancy provisioning
 * accessed much more often
 * by more people (devs and sysadmins) you trust

Therefore you can expect the magic of self-management to happen and avoid some common pitfalls:
 * keys of people who are gone staying forever
 * generic access keys to be passed around

And many more of the things you can expect when smart people you trust are able to take action easily when they see something wrong.

Every dev or sysadmin in the organisation can use it
----------------------------------------------------

The syncing rule is simple: if you have a certain access on a server, you can give the same access to somebody else. But you naturally cannot give yourself or another accesses you do not have.

This might seem straightforward but this is not what you get when you use a solution like puppet, chef or ansible. These provisioning solutions are mostly run as root on the destination server, therefore disallowing a non-root user to contribute. Even if it is to give somebody else the access you are already trusted with.



Installation
============

   ::

       sudo pip install synckeys


Configuration
=============

Create a :key: `keys.yml` file
---------------------------------


::

        fabriceb:
            key: ssh-rsa AAAA...ffY5+++j
            expires: ~
        simonc:
            key: ssh-rsa AABB...ffY5+++j
            expires: 2015-12-31


Create a :lock: `acl.yml` file
---------------------------------


::

      - name: superproject
        servers:
          - front.superproject.com
          - db.superproject.com
        users:
          ubuntu:
            sudoer: True
            authorized_keys:
              - simonc
              - fabriceb
          www-data:
            authorized_keys:
              - simonc
              - fabriceb
              - reynaldm
              - adrieng

      - name: otherproject
        servers:
          - 65.2.3.4
        users:
          root:
            sudoer: True
            authorized_keys:
              - fabriceb
          www-data:
            authorized_keys:
              - simonc
              - fabriceb



Usage
=====

Sync everything you are allowed to sync:

   ::

       synckeys --key-name yourkeyname


Sync a specific project:

   ::

       synckeys --key-name yourkeyname --project superproject


TODO :memo:
===========

-  [x] Remove expired keys
-  [ ] Remove all keys in keys.yml if they are on the server but not in acl.yml
-  [ ] Add an option to erase all keys that are not explicitly listed in acl.yml
