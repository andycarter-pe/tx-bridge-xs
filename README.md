# TX-BRIDGE-XS <img src="doc/Logo_CWE_TxDOT.png" align="right" alt="tx-bridge agency" height="80"> <br> <br>
## <i>Texas Bridge - Flood Warning Cross Section Web Server </i>

<img src="/doc/tx-bridge-logo-20220517.png" align="right"
     alt="tx-bridge logo" width="160" height="160">

**Description**:  A database of simplified bridge geometry was extracted from statewide LiDAR and DEMs for the State of Texas.  From the bridge database, it was necessary to produce interactive graphics estimating water depths for more than 19,000 bridges across Texas on an hourly basis, providing an eighteen-hour advance prediction.  These graphics are used to indicate instances when a bridge's superstructure, including beams and deck, may be at risk of flooding. <br><br>
Each cross section is cross-referenced with both the National Bridge Inventory database and the National Weather Service’s National Water Model (NWM) stream reach. Anticipated stream flows from the National Water Model are then converted into predictions of flood depths.

  - **Technology stack**: Scripts were all developed in Python 3.8.<br><br>
  - **Status**:  Version 0.1- Preliminary release. <br><br>
  - **Related Projects**: Bridge database was created using the TX-Bridge repository.  https://github.com/andycarter-pe/tx-bridge<br>

## Flask Server
This is a Flask server that serves interactive plotly graphics of a 'bridge envelope'.  Each bridge has a syntheic rating curve (depth vs flow rate) and knows what National Water Model stream reach that is crosses.

<img src="/doc/Flask_server_diagram.png" align="center"
     alt="tx-bridge logo" width="100%">

## Dockerfile
To build a container from this repository, clone to your local drive and build with the following command
```
docker build -t tx-bridge-xs .
```

## Docker Container
For convience, a container has been pre-built and pushed to DockerHub.  To pull this container to your machine...
```
docker build -t civileng127/tx-bridge-xs:20240216 .
```
To run this container, use the following command
```
docker run -p 5000:5000 civileng127/tx-bridge-xs:20240216
```

## Misc
For this server, a JSON for each bridge is created and staged on an S3 bucket prior to spinning up the web server.  This utilizes a script named 'create_bridge_json_files.py' in the misc folder.  This converts the bridge database sqlite created with 'TX-Bridge' for the State of Texas to individual JSON per uuid.  This database currently resides on S3 at s3://txbridge-data/test-upload/tx-bridge-geom.sqlite
