# Pre-req for the maintenance pipeline:


> [!NOTE]
> replace paths, share & server name as per your env.

---
## 1. Ensure:

- A share has been created on the remote. DC-01 is my server where i am hosting the share.
- A service account with RW permissions on the share.
## 2. Install CIFS utilty & smbclient:

```bash

sudo apt update

sudo apt install -y cifs-utils smbclient

````

## 3. Create a secure credentials file:

```bash

sudo nano /etc/samba/jenkins-artifacts.creds

```

File content:

```text

username=your_domain_user

password=your_password

domain=YOURDOMAIN

```

Set permissions:

```bash

sudo chmod 600 /etc/samba/jenkins-artifacts.creds

sudo chown root:root /etc/samba/jenkins-artifacts.creds

```

## 4. Create mount point:

```bash

sudo mkdir -p /mnt/jenkins-artifacts

sudo chown jenkins:jenkins /mnt/jenkins-artifacts

sudo chmod 750 /mnt/jenkins-artifacts

```
  
## 5. Create an entry in fstab for persistence across reboots:

```bash

sudo nano /etc/fstab

```

Add this entry:

```text

//dc-01.intra.wonderingpacket.com/jenkins-artifacts /mnt/jenkins-artifacts cifs credentials=/etc/samba/jenkins-artifacts.creds,uid=jenkins,gid=jenkins,dir_mode=0750,file_mode=0640,iocharset=utf8,nofail,_netdev 0 0

```
 

## 6. Reload & mount

```bash

sudo systemctl daemon-reload

sudo mount -a

```

## 7. Validation:

```bash

df -h | grep jenkins-artifacts

sudo -u jenkins touch /mnt/jenkins-artifacts/test.txt

sudo -u jenkins rm /mnt/jenkins-artifacts/test.txt

```