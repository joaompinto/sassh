# SETUP

1. Generate a GPG private/public keypair, *YOU SHOULD PROTECT THEY KEY WITH A PASSPHRASE .*, using the command:
```bash
   gpg --gen-key
```

2. Identify the id for the private key generated above:
```bash
   gpg --list-secret-keys | grep -e ^sec | cut -d "/" -f2| cut -d" " -f1
```

3. Append the following line to your ~/.bashrc, replace YOUR_GPG_KEY_ID with the id from 2.
```bash
   export SASSH_GPG_PUB_KEY="YOUR_GPG_KEY_ID"
```

4. Load the new profile
```bash
   . ~/.bashrc
```


