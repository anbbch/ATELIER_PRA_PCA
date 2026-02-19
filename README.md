------------------------------------------------------------------------------------------------------
ATELIER PRA/PCA
------------------------------------------------------------------------------------------------------
L’idée en 30 secondes : Cet atelier met en œuvre un **mini-PRA** sur **Kubernetes** en déployant une **application Flask** avec une **base SQLite** stockée sur un **volume persistant (PVC pra-data)** et des **sauvegardes automatiques réalisées chaque minute vers un second volume (PVC pra-backup)** via un **CronJob**. L’**image applicative est construite avec Packer** et le **déploiement orchestré avec Ansible**, tandis que Kubernetes assure la gestion des pods et de la disponibilité applicative. Nous observerons la différence entre **disponibilité** (recréation automatique des pods sans perte de données) et **reprise après sinistre** (perte volontaire du volume de données puis restauration depuis les backups), nous mesurerons concrètement les RTO et RPO, et comprendrons les limites d’un PRA local non répliqué. Cet atelier illustre de manière pratique les principes de continuité et de reprise d’activité, ainsi que le rôle respectif des conteneurs, du stockage persistant et des mécanismes de sauvegarde.
  
**Architecture cible :** Ci-dessous, voici l'architecture cible souhaitée.   
  
![Screenshot Actions](Architecture_cible.png)  
  
-------------------------------------------------------------------------------------------------------
Séquence 1 : Codespace de Github
-------------------------------------------------------------------------------------------------------
Objectif : Création d'un Codespace Github  
Difficulté : Très facile (~5 minutes)
-------------------------------------------------------------------------------------------------------
**Faites un Fork de ce projet**. Si besoin, voici une vidéo d'accompagnement pour vous aider à "Forker" un Repository Github : [Forker ce projet](https://youtu.be/p33-7XQ29zQ) 
  
Ensuite depuis l'onglet **[CODE]** de votre nouveau Repository, **ouvrez un Codespace Github**.
  
---------------------------------------------------
Séquence 2 : Création du votre environnement de travail
---------------------------------------------------
Objectif : Créer votre environnement de travail  
Difficulté : Simple (~10 minutes)
---------------------------------------------------
Vous allez dans cette séquence mettre en place un cluster Kubernetes K3d contenant un master et 2 workers, installer les logiciels Packer et Ansible. Depuis le terminal de votre Codespace copier/coller les codes ci-dessous étape par étape :  

**Création du cluster K3d**  
```
curl -s https://raw.githubusercontent.com/k3d-io/k3d/main/install.sh | bash
```
```
k3d cluster create pra \
  --servers 1 \
  --agents 2
```
**vérification de la création de votre cluster Kubernetes**  
```
kubectl get nodes
```
**Installation du logiciel Packer (création d'images Docker)**  
```
PACKER_VERSION=1.11.2
curl -fsSL -o /tmp/packer.zip \
  "https://releases.hashicorp.com/packer/${PACKER_VERSION}/packer_${PACKER_VERSION}_linux_amd64.zip"
sudo unzip -o /tmp/packer.zip -d /usr/local/bin
rm -f /tmp/packer.zip
```
**Installation du logiciel Ansible**  
```
python3 -m pip install --user ansible kubernetes PyYAML jinja2
export PATH="$HOME/.local/bin:$PATH"
ansible-galaxy collection install kubernetes.core
```
  
---------------------------------------------------
Séquence 3 : Déploiement de l'infrastructure
---------------------------------------------------
Objectif : Déployer l'infrastructure sur le cluster Kubernetes
Difficulté : Facile (~15 minutes)
---------------------------------------------------  
Nous allons à présent déployer notre infrastructure sur Kubernetes. C'est à dire, créér l'image Docker de notre application Flask avec Packer, déposer l'image dans le cluster Kubernetes et enfin déployer l'infratructure avec Ansible (Création du pod, création des PVC et les scripts des sauvegardes aututomatiques).  

**Création de l'image Docker avec Packer**  
```
packer init .
packer build -var "image_tag=1.0" .
docker images | head
```
  
**Import de l'image Docker dans le cluster Kubernetes**  
```
k3d image import pra/flask-sqlite:1.0 -c pra
```
  
**Déploiment de l'infrastructure dans Kubernetes**  
```
ansible-playbook ansible/playbook.yml
```
  
**Forward du port 8080 qui est le port d'exposition de votre application Flask**  
```
kubectl -n pra port-forward svc/flask 8080:80 >/tmp/web.log 2>&1 &
```
  
---------------------------------------------------  
**Réccupération de l'URL de votre application Flask**. Votre application Flask est déployée sur le cluster K3d. Pour obtenir votre URL cliquez sur l'onglet **[PORTS]** dans votre Codespace (à coté de Terminal) et rendez public votre port 8080 (Visibilité du port). Ouvrez l'URL dans votre navigateur et c'est terminé.  

**Les routes** à votre disposition sont les suivantes :  
1. https://...**/** affichera dans votre navigateur "Bonjour tout le monde !".
2. https://...**/health** pour voir l'état de santé de votre application.
3. https://...**/add?message=test** pour ajouter un message dans votre base de données SQLite.
4. https://...**/count** pour afficher le nombre de messages stockés dans votre base de données SQLite.
5. https://...**/consultation** pour afficher les messages stockés dans votre base de données.

<img width="1823" height="247" alt="image" src="https://github.com/user-attachments/assets/9a560e99-c773-41d0-ae5e-83e3beb18ecf" />
<img width="2237" height="1107" alt="image" src="https://github.com/user-attachments/assets/8f6a418d-8571-4c80-a607-c8046478a58c" />


---------------------------------------------------  
### Processus de sauvegarde de la BDD SQLite

Grâce à une tâche CRON déployée par Ansible sur le cluster Kubernetes (un CronJob), toutes les minutes une sauvegarde de la BDD SQLite est faite depuis le PVC pra-data vers le PCV pra-backup dans Kubernetes.  

Pour visualiser les sauvegardes périodiques déposées dans le PVC pra-backup, coller les commandes suivantes dans votre terminal Codespace :  

```
kubectl -n pra run debug-backup \
  --rm -it \
  --image=alpine \
  --overrides='
{
  "spec": {
    "containers": [{
      "name": "debug",
      "image": "alpine",
      "command": ["sh"],
      "stdin": true,
      "tty": true,
      "volumeMounts": [{
        "name": "backup",
        "mountPath": "/backup"
      }]
    }],
    "volumes": [{
      "name": "backup",
      "persistentVolumeClaim": {
        "claimName": "pra-backup"
      }
    }]
  }
}'
```
```
ls -lh /backup
```
**Pour sortir du cluster et revenir dans le terminal**
```
exit
```

---------------------------------------------------
Séquence 4 : 💥 Scénarios de crash possibles  
Difficulté : Facile (~30 minutes)
---------------------------------------------------
### 🎬 **Scénario 1 : PCA — Crash du pod**  
Nous allons dans ce scénario **détruire notre Pod Kubernetes**. Ceci simulera par exemple la supression d'un pod accidentellement, ou un pod qui crash, ou un pod redémarré, etc..

**Destruction du pod :** Ci-dessous, la cible de notre scénario   
  
![Screenshot Actions](scenario1.png)  

Nous perdons donc ici notre application mais pas notre base de données puisque celle-ci est déposée dans le PVC pra-data hors du pod.  

Copier/coller le code suivant dans votre terminal Codespace pour détruire votre pod :
```
kubectl -n pra get pods
```
<img width="957" height="214" alt="image" src="https://github.com/user-attachments/assets/f074e6e1-3455-4dfa-83a8-cb64e9f7cd2a" />

Notez le nom de votre pod qui est différent pour tout le monde.  
Supprimez votre pod (pensez à remplacer <nom-du-pod-flask> par le nom de votre pod).  
Exemple : kubectl -n pra delete pod flask-7c4fd76955-abcde  
```
kubectl -n pra delete pod <nom-du-pod-flask>
```
<img width="1271" height="58" alt="image" src="https://github.com/user-attachments/assets/b43603ef-1e50-4c0b-a2cc-5adf1ede3f33" />

**Vérification de la suppression de votre pod**
```
kubectl -n pra get pods
```
<img width="1024" height="210" alt="image" src="https://github.com/user-attachments/assets/b6578b83-8ec0-49fe-9274-1245078c781b" />

👉 **Le pod a été reconstruit sous un autre identifiant**.  
Forward du port 8080 du nouveau service  
```
kubectl -n pra port-forward svc/flask 8080:80 >/tmp/web.log 2>&1 &
```
<img width="1519" height="120" alt="image" src="https://github.com/user-attachments/assets/deb592f2-4476-4449-9f94-a36a8bcb7058" />

Observez le résultat en ligne  
https://...**/consultation** -> Vous n'avez perdu aucun message.

<img width="1883" height="296" alt="image" src="https://github.com/user-attachments/assets/d33c6644-dff3-41de-b03d-428bf79a0446" />

👉 Kubernetes gère tout seul : Aucun impact sur les données ou sur votre service (PVC conserve la DB et le pod est reconstruit automatiquement) -> **C'est du PCA**. Tout est automatique et il n'y a aucune rupture de service.
  
---------------------------------------------------
### 🎬 **Scénario 2 : PRA - Perte du PVC pra-data** 
Nous allons dans ce scénario **détruire notre PVC pra-data**. C'est à dire nous allons suprimer la base de données en production. Ceci simulera par exemple la corruption de la BDD SQLite, le disque du node perdu, une erreur humaine, etc. 💥 Impact : IL s'agit ici d'un impact important puisque **la BDD est perdue**.  

**Destruction du PVC pra-data :** Ci-dessous, la cible de notre scénario   
  
![Screenshot Actions](scenario2.png)  

🔥 **PHASE 1 — Simuler le sinistre (perte de la BDD de production)**  
Copier/coller le code suivant dans votre terminal Codespace pour détruire votre base de données :
```
kubectl -n pra scale deployment flask --replicas=0
```
```
kubectl -n pra patch cronjob sqlite-backup -p '{"spec":{"suspend":true}}'
```
```
kubectl -n pra delete job --all
```
```
kubectl -n pra delete pvc pra-data
```
👉 Vous pouvez vérifier votre application en ligne, la base de données est détruite et la service n'est plus accéssible.  

<img width="1565" height="294" alt="image" src="https://github.com/user-attachments/assets/b06ac1d4-6591-43a4-bac3-e8435416d512" />
<img width="1640" height="894" alt="image" src="https://github.com/user-attachments/assets/82e99d95-1142-48c7-9279-92a4c4c11ef2" />


✅ **PHASE 2 — Procédure de restauration**  
Recréer l’infrastructure avec un PVC pra-data vide.  
```
kubectl apply -f k8s/
```
Vérification de votre application en ligne.  
Forward du port 8080 du service pour tester l'application en ligne.  
```
kubectl -n pra port-forward svc/flask 8080:80 >/tmp/web.log 2>&1 &
```
<img width="1536" height="310" alt="image" src="https://github.com/user-attachments/assets/04c31d57-3309-4790-9547-850563eb53c2" />

https://...**/count** -> =0.  
<img width="1165" height="317" alt="image" src="https://github.com/user-attachments/assets/8dab2d8b-41da-40df-9ed1-5d013d3e5ca8" />

https://...**/consultation** Vous avez perdu tous vos messages.  
<img width="1075" height="272" alt="image" src="https://github.com/user-attachments/assets/5365d157-a2f2-40e6-b1d2-adc28590ddd6" />

Retaurez votre BDD depuis le PVC Backup.  
```
kubectl apply -f pra/50-job-restore.yaml
```
👉 Vous pouvez vérifier votre application en ligne, **votre base de données a été restaureé** et tous vos messages sont bien présents.  

Relance des CRON de sauvgardes.  
```
kubectl -n pra patch cronjob sqlite-backup -p '{"spec":{"suspend":false}}'
```
👉 Nous n'avons pas perdu de données mais Kubernetes ne gère pas la restauration tout seul. Nous avons du protéger nos données via des sauvegardes régulières (du PVC pra-data vers le PVC pra-backup). -> **C'est du PRA**. Il s'agit d'une stratégie de sauvegarde avec une procédure de restauration.  

---------------------------------------------------
Séquence 5 : Exercices  
Difficulté : Moyenne (~45 minutes)
---------------------------------------------------
**Complétez et documentez ce fichier README.md** pour répondre aux questions des exercices.  
Faites preuve de pédagogie et soyez clair dans vos explications et procedures de travail.  

**Exercice 1 :**  
Quels sont les composants dont la perte entraîne une perte de données ?  
  
Dans cette architecture, les données persistantes donc les messages de l’application, sont stockées dans un fichier SQLite situé dans le volume monté sur /data.
Les composants dont la perte entraîne une perte de données sont :

1) Le PVC pra-data:
  - C’est le volume persistant qui contient le fichier SQLite (/data/app.db).
  - Si ce PVC est supprimé, la base SQLite est supprimée aussi.

2) Le PVC pra-backup
  - C’est le volume persistant qui contient les sauvegardes générées par le CronJob.
  - Si ce PVC est supprimé, on perd l’historique des backups.
  - Donc on perd la capacité de restaurer en cas de sinistre.

3) Ici, le disque du node
  les PVC reposent sur le stockage local du cluster (disque du node). Donc si le node disparaît ou est recréé → les volumes disparaissent aussi.

**Exercice 2 :**  
Expliquez nous pourquoi nous n'avons pas perdu les données lors de la supression du PVC pra-data  
  
Lorsqu’on supprime le Pod Flask, on ne supprime pas les données, car :

1) La base SQLite n’est pas stockée dans le Pod :
  - Le Pod est éphémère
  - Les données applicatives ne sont pas stockées dans son filesystem interne

2) La base SQLite est stockée dans un PVC
Le fichier app.db est stocké dans le volume persistant pra-data monté sur /data.

Donc, même si le Pod est détruit :
  - Kubernetes recrée automatiquement un nouveau Pod (grâce au Deployment)
  - Le nouveau Pod remonte le même PVC
  - La base SQLite est retrouvée intacte

Ainsi la suppression du Pod n’entraîne pas de perte de données, car les données sont dans un stockage persistant (PVC), séparé du Pod.

**Exercice 3 :**  
Quels sont les RTO et RPO de cette solution ?  
  
Le RTO (Recovery Time Objective) correspond au temps maximum acceptable pour restaurer le service.
Ici :
  - Si le Pod crash et Kubernetes le recrée automatiquement en quelques secondes
  - Le service redevient donc disponible très vite
RTO PCA (perte du pod) : ~ quelques secondes (temps de recréation du Pod)

Le RPO (Recovery Point Objective) correspond à la quantité maximale de données qu’on accepte de perdre.
Ici, la sauvegarde est faite par CronJob toutes les minutes :
  - RPO PRA (perte du PVC pra-data) : ~ 1 minute car on restaure depuis la dernière sauvegarde

**Exercice 4 :**  
Pourquoi cette solution (cet atelier) ne peux pas être utilisé dans un vrai environnement de production ? Que manque-t-il ?   
  
Cette solution est pédagogique mais pas production-ready pour plusieurs raisons :
1) SQLite n’est pas adapté à Kubernetes en production
  - SQLite est un fichier local
  - Risque de corruption en cas d’écriture concurrente
  - Pas fait pour plusieurs pods

2) Le stockage est local au node
Dans ce TP, les volumes sont sur le disque du node :
  - Si le node est perdu → les PVC sont perdus
  - En production, il faut du stockage réseau (type NFS, Ceph, EBS, Azure Disk, etc.)

3) Pas de haute disponibilité (HA)
  - 1 seul pod Flask
  - 1 seule base SQLite
Si il y a plusieurs replicas alors SQLite devient un problème

4) Sauvegarde “artisanale”
  - Copier un fichier .db est fragile
  - Pas de gestion de cohérence (verrouillage SQLite, snapshot cohérent, etc.)
  - Pas de chiffrement
  - Pas de rétention (combien de backups ?)

5) Pas de monitoring / alerting
  - Aucun système d’alertes si le CronJob échoue
  - Aucun log centralisé
  - Pas de supervision
  
**Exercice 5 :**  
Proposez une archtecture plus robuste.   
  
Voici une architecture beaucoup plus robuste et réaliste pour une production :

1) Base de données dédiée (PostgreSQL ou MySQL)
  - Déployée en cluster (ou service managé : RDS/Azure Database)
  - Faire une réplication
  - Backups intégrés
  - Point-in-time recovery possible

2) Application Flask stateless (plusieurs pods)
  - Plusieurs replicas (ex: 2 ou 3)
  - Load balancing via Service / Ingress
  - Auto-scaling possible

3) Stockage persistant réseau
  - Pour les fichiers (uploads, etc.)
  - Avec une StorageClass robuste (EBS, Azure Disk, Ceph…)

4) Backup & restore professionnel
  - Backup DB via outils dédiés (pg_dump, WAL, snapshots)
  - Stockage des backups hors cluster (S3, Blob Storage)
  - Politique de rétention (7 jours / 30 jours…)

5) Observabilité
  - Logs centralisés (ELK, Loki)
  - Monitoring (Prometheus/Grafana)
  - Alerting (Slack/email)

---------------------------------------------------
Séquence 6 : Ateliers  
Difficulté : Moyenne (~2 heures)
---------------------------------------------------
### **Atelier 1 : Ajoutez une fonctionnalité à votre application**  
**Ajouter une route GET /status** dans votre application qui affiche en JSON :
* count : nombre d’événements en base
* last_backup_file : nom du dernier backup présent dans /backup
* backup_age_seconds : âge du dernier backup

*..**Déposez ici une copie d'écran** de votre réussite..*

---------------------------------------------------
### **Atelier 2 : Choisir notre point de restauration**  
Aujourd’hui nous restaurobs “le dernier backup”. Nous souhaitons **ajouter la capacité de choisir un point de restauration**.

*..Décrir ici votre procédure de restauration (votre runbook)..*  
  
---------------------------------------------------
Evaluation
---------------------------------------------------
Cet atelier PRA PCA, **noté sur 20 points**, est évalué sur la base du barème suivant :  
- Série d'exerices (5 points)
- Atelier N°1 - Ajout d'un fonctionnalité (4 points)
- Atelier N°2 - Choisir son point de restauration (4 points)
- Qualité du Readme (lisibilité, erreur, ...) (3 points)
- Processus travail (quantité de commits, cohérence globale, interventions externes, ...) (4 points) 

