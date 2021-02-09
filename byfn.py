import os
import time
import shutil
import subprocess

import click
import docker

client = docker.from_env() 

def generate_certs(config: str, output: str):
    subprocess.run(
        ['cryptogen', 'generate', '--config', config, '--output', output])


def generate_channel_artifacts(consortium: str, channel: str, output: str):
    system_channel = f'{consortium}-sys-channel'
    subprocess.run([
        'configtxgen',
        '-profile',
        'TwoOrgsOrdererGenesis',
        '-channelID',
        system_channel,
        '-outputBlock',
        os.path.join(output, 'genesis.block'),
    ])
    subprocess.run([
        'configtxgen',
        '-profile',
        'TwoOrgsChannel',
        '-channelID',
        channel,
        '-outputCreateChannelTx',
        os.path.join(output, f'{channel}.tx'),
    ])
    subprocess.run([
        'configtxgen',
        '-profile',
        'TwoOrgsChannel',
        '-channelID',
        channel,
        '-asOrg',
        'Org1MSP',
        '-outputAnchorPeersUpdate',
        os.path.join(output, f'Org1MSPanchors.tx'),
    ])
    subprocess.run([
        'configtxgen',
        '-profile',
        'TwoOrgsChannel',
        '-channelID',
        channel,
        '-asOrg',
        'Org2MSP',
        '-outputAnchorPeersUpdate',
        os.path.join(output, f'Org2MSPanchors.tx'),
    ])


def create_channel(channel: str):
    mspconfig = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/users/Admin@org1.example.com/msp'
    cafile = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem'
    crypto_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations/org1.example.com/peers/peer0.org1.example.com'
    subprocess.run([
        'docker', 'exec', '-it', '-e', 'CORE_PEER_ID=cli', '-e',
        'CORE_PEER_ADDRESS=peer0.org1.example.com:7051', '-e',
        'CORE_PEER_LOCALMSPID=Org1MSP', '-e', 'CORE_PEER_TLS_ENABLED=true',
        '-e', 'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')), '-e',
        'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')), '-e',
        'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')), '-e',
        f'CORE_PEER_MSPCONFIGPATH={mspconfig}', 'cli', 'peer', 'channel',
        'create', '-o', 'orderer.example.com:7050', '-c', channel, '-f',
        f'./channel-artifacts/{channel}.tx', '--tls', 'true', '--cafile',
        cafile
    ])


def join_channel(org: str, peer: str, port: int, channel: str):
    base_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto/peerOrganizations'
    mspconfig = f'{base_path}/{org}.example.com/users/Admin@{org}.example.com/msp'
    crypto_path = f'{base_path}/{org}.example.com/peers/{peer}.{org}.example.com'
    subprocess.run([
        'docker',
        'exec',
        '-it',
        '-e',
        f'CORE_PEER_ID=cli',
        '-e',
        f'CORE_PEER_ADDRESS={peer}.{org}.example.com:{port}',
        '-e',
        f'CORE_PEER_LOCALMSPID={org.title()}MSP',
        '-e',
        'CORE_PEER_TLS_ENABLED=true',
        '-e',
        'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')),
        '-e',
        'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')),
        '-e',
        'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')),
        '-e',
        f'CORE_PEER_MSPCONFIGPATH={mspconfig}',
        'cli',
        'peer',
        'channel',
        'join',
        '-b',
        f'{channel}.block',
    ])


def update_anchor_peer(org: str, peer: str, port: int, channel: str):
    base_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto'
    mspconfig = f'{base_path}/peerOrganizations/{org}.example.com/users/Admin@{org}.example.com/msp'
    crypto_path = f'{base_path}/peerOrganizations/{org}.example.com/peers/{peer}.{org}.example.com'
    cafile = f'{base_path}/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem'
    subprocess.run([
        'docker', 'exec', '-it',
        '-e', 'CORE_PEER_ID=cli',
        '-e', f'CORE_PEER_ADDRESS={peer}.{org}.example.com:{port}',
        '-e', f'CORE_PEER_LOCALMSPID={org.title()}MSP',
        '-e', 'CORE_PEER_TLS_ENABLED=true',
        '-e', 'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')), 
        '-e', 'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')),
        '-e', 'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')),
        '-e', f'CORE_PEER_MSPCONFIGPATH={mspconfig}',
        'cli',
        'peer', 'channel', 'update',
        '-o', 'orderer.example.com:7050',
        '-c', channel,
        '-f', f'./channel-artifacts/{org.title()}MSPanchors.tx',
        '--tls', 'true', '--cafile', cafile
    ])


def install_chaincode(org: str, peer: str, port, chaincode: str, version: str):
    base_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto'
    mspconfig = f'{base_path}/peerOrganizations/{org}.example.com/users/Admin@{org}.example.com/msp'
    crypto_path = f'{base_path}/peerOrganizations/{org}.example.com/peers/{peer}.{org}.example.com'
    subprocess.run([
        'docker', 'exec', '-it',
        '-e', 'CORE_PEER_ID=cli',
        '-e', f'CORE_PEER_ADDRESS={peer}.{org}.example.com:{port}',
        '-e', f'CORE_PEER_LOCALMSPID={org.title()}MSP',
        '-e', 'CORE_PEER_TLS_ENABLED=true',
        '-e', 'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')), 
        '-e', 'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')),
        '-e', 'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')),
        '-e', f'CORE_PEER_MSPCONFIGPATH={mspconfig}',
        'cli',
        'peer', 'chaincode', 'install',
        '-l', 'golang',
        '-n', chaincode,
        '-v', version,
        '-p', os.path.join('github.com', 'chaincode', chaincode)
    ])

def instantiate_chaincode(org: str, peer: str, port: int, channel: str, chaincode: str, version: str):
    base_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto'
    mspconfig = f'{base_path}/peerOrganizations/{org}.example.com/users/Admin@{org}.example.com/msp'
    crypto_path = f'{base_path}/peerOrganizations/{org}.example.com/peers/{peer}.{org}.example.com'
    cafile = f'{base_path}/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem'
    subprocess.run([
        'docker', 'exec', '-it',
        '-e', 'CORE_PEER_ID=cli',
        '-e', f'CORE_PEER_ADDRESS={peer}.{org}.example.com:{port}',
        '-e', f'CORE_PEER_LOCALMSPID={org.title()}MSP',
        '-e', 'CORE_PEER_TLS_ENABLED=true',
        '-e', 'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')), 
        '-e', 'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')),
        '-e', 'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')),
        '-e', f'CORE_PEER_MSPCONFIGPATH={mspconfig}',
        'cli',
        'peer', 'chaincode', 'instantiate',
        '-o', 'orderer.example.com:7050',
        '-C', channel,
        '-l', 'golang',
        '-n', chaincode,
        '-v', version,
        '-c', '{"Args":["init","a","100","b","200"]}',
        '-P', "OR ('Org1MSP.peer','Org2MSP.peer')",
        '--tls', 'true', '--cafile', cafile,
    ])

def query(org: str, peer: str, port: int, channel: str, chaincode: str):
    base_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto'
    mspconfig = f'{base_path}/peerOrganizations/{org}.example.com/users/Admin@{org}.example.com/msp'
    crypto_path = f'{base_path}/peerOrganizations/{org}.example.com/peers/{peer}.{org}.example.com'
    subprocess.run([
        'docker', 'exec', '-it',
        '-e', 'CORE_PEER_ID=cli',
        '-e', f'CORE_PEER_ADDRESS={peer}.{org}.example.com:{port}',
        '-e', f'CORE_PEER_LOCALMSPID={org.title()}MSP',
        '-e', 'CORE_PEER_TLS_ENABLED=true',
        '-e', 'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')), 
        '-e', 'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')),
        '-e', 'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')),
        '-e', f'CORE_PEER_MSPCONFIGPATH={mspconfig}',
        'cli',
        'peer', 'chaincode', 'query',
        '-C', channel,
        '-n', chaincode,
        '-c', '{"Args":["query","a"]}'
    ])

def invoke(org: str, peer: str, port: int, channel: str, chaincode: str):
    base_path = '/opt/gopath/src/github.com/hyperledger/fabric/peer/crypto'
    mspconfig = f'{base_path}/peerOrganizations/{org}.example.com/users/Admin@{org}.example.com/msp'
    crypto_path = f'{base_path}/peerOrganizations/{org}.example.com/peers/{peer}.{org}.example.com'
    cafile = f'{base_path}/ordererOrganizations/example.com/orderers/orderer.example.com/msp/tlscacerts/tlsca.example.com-cert.pem'
    subprocess.run([
        'docker', 'exec', '-it',
        '-e', 'CORE_PEER_ID=cli',
        '-e', f'CORE_PEER_ADDRESS={peer}.{org}.example.com:{port}',
        '-e', f'CORE_PEER_LOCALMSPID={org.title()}MSP',
        '-e', 'CORE_PEER_TLS_ENABLED=true',
        '-e', 'CORE_PEER_TLS_CERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.crt')), 
        '-e', 'CORE_PEER_TLS_KEY_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'server.key')),
        '-e', 'CORE_PEER_TLS_ROOTCERT_FILE={}'.format(
            os.path.join(crypto_path, 'tls', 'ca.crt')),
        '-e', f'CORE_PEER_MSPCONFIGPATH={mspconfig}',
        'cli',
        'peer', 'chaincode', 'invoke',
        '-C', channel,
        '-n', chaincode,
        '-c', '{"Args":["invoke","a","b","10"]}',
        '--peerAddresses', f'{peer}.{org}.example.com:{port}',
        '--tlsRootCertFiles', os.path.join(crypto_path, 'tls', 'ca.crt'),
        '-o', 'orderer.example.com:7050',
        '--tls', 'true', '--cafile', cafile
    ])

@click.group()
@click.option('--workdir', default=os.getcwd())
@click.pass_context
def cli(ctx: click.Context, workdir: str):
    ctx.obj['workdir'] = workdir


@cli.command()
@click.pass_context
def start(ctx: click.Context):
    crypto_config = os.path.join(ctx.obj['workdir'], 'crypto-config.yaml')
    crypto_output = os.path.join(ctx.obj['workdir'], 'crypto-config')
    generate_certs(crypto_config, crypto_output)

    artifact_output = os.path.join(ctx.obj['workdir'], 'channel-artifacts')
    if not os.path.exists(artifact_output):
        os.mkdir(artifact_output)
    generate_channel_artifacts('byfn', 'mychannel', artifact_output)

    subprocess.run(['docker-compose', 'up', '-d'])

    create_channel('mychannel')
    join_channel('org1', 'peer0', 7051, 'mychannel')
    join_channel('org1', 'peer1', 8051, 'mychannel')
    join_channel('org2', 'peer0', 9051, 'mychannel')
    join_channel('org2', 'peer1', 10051, 'mychannel')

    update_anchor_peer('org1', 'peer0', 7051, 'mychannel')
    update_anchor_peer('org2', 'peer0', 9051, 'mychannel')

    install_chaincode('org1', 'peer0', 7051, 'ex02', 'v1.0')
    install_chaincode('org1', 'peer1', 8051, 'ex02', 'v1.0')
    install_chaincode('org2', 'peer0', 9051, 'ex02', 'v1.0')
    install_chaincode('org2', 'peer1', 10051, 'ex02', 'v1.0')

    instantiate_chaincode('org1', 'peer0', 7051, 'mychannel', 'ex02', 'v1.0')

    time.sleep(5)
    query('org1', 'peer0', 7051, 'mychannel', 'ex02')
    time.sleep(5)
    invoke('org1', 'peer0', 7051, 'mychannel', 'ex02')
    time.sleep(5)
    query('org1', 'peer0', 7051, 'mychannel', 'ex02')

@cli.command()
@click.pass_context
def clean(ctx: click.Context):
    shutil.rmtree(os.path.join(ctx.obj['workdir'], 'crypto-config'),
                  ignore_errors=True)
    shutil.rmtree(os.path.join(ctx.obj['workdir'], 'channel-artifacts'),
                  ignore_errors=True)
    subprocess.run(['docker-compose', 'down', '-v'])
    
    clean_containers()
    clean_images()

def clean_containers():
    for container in client.containers.list():
        if container.name.startswith('dev-peer'):
            container.stop()
            time.sleep(5)
            container.remove()

def clean_images():
    for image in client.images.list():
        for tag in image.tags:
            if tag.startswith('dev-peer'):
                client.images.remove(tag)


if __name__ == '__main__':
    cli(obj=dict())