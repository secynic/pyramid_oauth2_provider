0.3.0 (TBD)
===========

- Python 3 support (#9)
- Removed epdb from create_client_credntials.py (#10)
- Fixed TypeError in OauthAuthenticationPolicy._get_auth_token (#14)
- Added scrypt hashing/salting of client secret - 
  new requirement: cryptography (#16)
- Changed/deprecated isRevoked() to is_revoked() in Oauth2Client, Oauth2Code, 
  and Oauth2Token (#16)
- Changed/deprecated asJSON() to as_json() in Oauth2Token (#16)
- Changed String DB columns to Unicode (#16)
- Added CHANGES.md and requirements.txt (#16)
- Code style fixes (#16)