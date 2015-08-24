synckeys
========

Le but du projet synckeys est de faciliter les interventions des Theodoers
sur les serveurs de nos projets tout en veillant à respecter certaines
règles de sécurité.

Ce repository centralise les clés ssh des theodoers dans le fichier
:key: `keys.yml`_ et leurs droits sur les différents serveurs dans le
fichier :lock: `acl.yml`_.

Pour mettre à jour les clés de tous les serveurs sur lesquels on a les
droits, lancer :

::

    python synckeys.py --key-name fabriceb

Installation
------------

Ce projet nécessite d’avoir déjà installé ``python`` et ``ansible`` (v
1.9.0.1) sur sa machine.

Les serveurs
------------

Le fichier :lock: `acl.yml`_ liste les serveurs, leurs utilisateurs (au
sens unix, e.g. www-data, operator) et les clés autorisées de la façon
suivante:

::

      - name: copadia
        servers:
          - copadia.com
          - preprod.copadia.com
        users:
          operator:
            sudoer: True
            authorized_keys:
              - simonc
              - fabriceb
              - dev_support

Ajouter une clé à un serveur
----------------------------

1. Ajouter sa clé à :key: `keys.yml`_.

Pour ceux qui savent quand ils vont partir, ne pas oublier la date
d’expiration:

::

        fabriceb:
            key: ssh-rsa AAAA...ffY5+++j
            expires: 2015-04-01

2. Ajouter sa clé au serveur voulu dans :lock: `acl.yml`_. Vérifier que
   la clé de **l’architecte du projet** est bien présente. Les
   développeurs du support y auront automatiquement accès grâce au
   mécanisme de `master key`_.

3. Si le serveur n’est pas encore présent dans :lock: `acl.yml`_,
   demander à Synalabs d’ajouter la clé de l’architecte au serveur

    **ATTENTION** : il ne faut pas que la clé soit ajoutée au
    provisioning (via PR) au projet, sinon elle ne sera plus gérée par
    ce repository

4. Merger la PR sur ce repo et demander à quelqu’un qui a déjà accès au
   serveur d’executer la commande suivante (en local dans le répertoire
   du dossier synckeys, après avoir mis à jour son repo):

   ::

       python synckeys.py --key-name fabriceb

TODO :memo:
-----------

-  [x] Possibilité de supprimer d’anciennnes clés
-  [ ] Synchroniser tous les accès d’un user d’un coup (changer le
   module authorized\_key)

.. _keys.yml: keys.yml
.. _acl.yml: acl.yml
.. _master key: #master-keys
