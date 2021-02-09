package main

import (
	"fmt"
	"io/ioutil"
	"log"
	"os"
	"path/filepath"
	"strings"
	"time"

	"gopkg.in/yaml.v3"
)

type TopLevel struct {
	Profiles      map[string]*Profile        `yaml:"Profiles"`
	Organizations []*Organization            `yaml:"Organizations"`
	Channel       *Profile                   `yaml:"Channel"`
	Application   *Application               `yaml:"Application"`
	Orderer       *Orderer                   `yaml:"Orderer"`
	Capabilities  map[string]map[string]bool `yaml:"Capabilities"`
	Resources     *Resources                 `yaml:"Resources"`
}

// Profile encodes orderer/application configuration combinations for the
// configtxgen tool.
type Profile struct {
	Consortium   string                 `yaml:"Consortium"`
	Application  *Application           `yaml:"Application"`
	Orderer      *Orderer               `yaml:"Orderer"`
	Consortiums  map[string]*Consortium `yaml:"Consortiums"`
	Capabilities map[string]bool        `yaml:"Capabilities"`
	Policies     map[string]*Policy     `yaml:"Policies"`
}

// Policy encodes a channel config policy
type Policy struct {
	Type string `yaml:"Type"`
	Rule string `yaml:"Rule"`
}

// Consortium represents a group of organizations which may create channels
// with each other
type Consortium struct {
	Organizations []*Organization `yaml:"Organizations"`
}

// Application encodes the application-level configuration needed in config
// transactions.
type Application struct {
	Organizations []*Organization    `yaml:"Organizations"`
	Capabilities  map[string]bool    `yaml:"Capabilities"`
	Resources     *Resources         `yaml:"Resources"`
	Policies      map[string]*Policy `yaml:"Policies"`
	ACLs          map[string]string  `yaml:"ACLs"`
}

// Resources encodes the application-level resources configuration needed to
// seed the resource tree
type Resources struct {
	DefaultModPolicy string
}

// Organization encodes the organization-level configuration needed in
// config transactions.
type Organization struct {
	Name     string             `yaml:"Name"`
	ID       string             `yaml:"ID"`
	MSPDir   string             `yaml:"MSPDir"`
	MSPType  string             `yaml:"MSPType"`
	Policies map[string]*Policy `yaml:"Policies"`

	// Note: Viper deserialization does not seem to care for
	// embedding of types, so we use one organization struct
	// for both orderers and applications.
	AnchorPeers      []*AnchorPeer `yaml:"AnchorPeers"`
	OrdererEndpoints []string      `yaml:"OrdererEndpoints"`

	// AdminPrincipal is deprecated and may be removed in a future release
	// it was used for modifying the default policy generation, but policies
	// may now be specified explicitly so it is redundant and unnecessary
	AdminPrincipal string `yaml:"AdminPrincipal"`
}

// AnchorPeer encodes the necessary fields to identify an anchor peer.
type AnchorPeer struct {
	Host string `yaml:"Host"`
	Port int    `yaml:"Port"`
}

// ConfigMetadata from etcdraft
type ConfigMetadata struct {
	Consenters []*Consenter `yaml:"Consenters"`
}

// Consenter from etcdraft
type Consenter struct {
	Host          string `yaml:"Host"`
	Port          uint32 `yaml:"Port"`
	ClientTLSCert string `yaml:"ClientTLSCert"`
	ServerTLSCert string `yaml:"ServerTLSCert"`
}

// Orderer contains configuration which is used for the
// bootstrapping of an orderer by the provisional bootstrapper.
type Orderer struct {
	OrdererType   string             `yaml:"OrdererType"`
	Addresses     []string           `yaml:"Addresses"`
	BatchTimeout  time.Duration      `yaml:"BatchTimeout"`
	BatchSize     BatchSize          `yaml:"BatchSize"`
	Kafka         Kafka              `yaml:"Kafka"`
	EtcdRaft      *ConfigMetadata    `yaml:"EtcdRaft"`
	Organizations []*Organization    `yaml:"Organizations"`
	MaxChannels   uint64             `yaml:"MaxChannels"`
	Capabilities  map[string]bool    `yaml:"Capabilities"`
	Policies      map[string]*Policy `yaml:"Policies"`
}

// BatchSize contains configuration affecting the size of batches.
type BatchSize struct {
	MaxMessageCount   uint32 `yaml:"MaxMessageCount"`
	AbsoluteMaxBytes  uint32 `yaml:"AbsoluteMaxBytes"`
	PreferredMaxBytes uint32 `yaml:"PreferredMaxBytes"`
}

// Kafka contains configuration for the Kafka-based orderer.
type Kafka struct {
	Brokers []string `yaml:"Brokers"`
}

var (
	OrganizationMap = map[string]int{
		"org1": 7051,
		"org2": 9051,
	}

	PeerOrganizationsDir    = filepath.Join("crypto-config", "peerOrganizations")
	OrdererOrganizationsDir = filepath.Join("crypto-config", "ordererOrganizations")
)

func main() {
	organizations := make([]*Organization, 0, 2)
	for orgName, anchorPort := range OrganizationMap {
		domain := fmt.Sprintf("%s.example.com", orgName)
		mspID := fmt.Sprintf("%sMSP", strings.Title(orgName))
		organization := &Organization{
			Name:   mspID,
			ID:     mspID,
			MSPDir: filepath.Join(PeerOrganizationsDir, domain, "msp"),
			Policies: map[string]*Policy{
				"Readers": {
					Type: "Signature",
					Rule: fmt.Sprintf(`OR('%s.admin', '%s.peer', '%s.client')`, mspID, mspID, mspID),
				},
				"Writers": {
					Type: "Signature",
					Rule: fmt.Sprintf(`OR('%s.admin', '%s.client')`, mspID, mspID),
				},
				"Admins": {
					Type: "Signature",
					Rule: fmt.Sprintf(`OR('%s.admin')`, mspID),
				},
			},
			AnchorPeers: []*AnchorPeer{
				{
					Host: fmt.Sprintf("peer0.%s.example.com", orgName),
					Port: anchorPort,
				},
			},
		}
		organizations = append(organizations, organization)
	}

	topLevel := &TopLevel{
		Profiles: map[string]*Profile{
			"TwoOrgsOrdererGenesis": {
				Policies: map[string]*Policy{
					"Readers": {
						Type: "ImplicitMeta",
						Rule: "ANY Readers",
					},
					"Writers": {
						Type: "ImplicitMeta",
						Rule: "ANY Writers",
					},
					"Admins": {
						Type: "ImplicitMeta",
						Rule: "MAJORITY Admins",
					},
				},
				Capabilities: map[string]bool{
					"V1_4_3": true,
					"V1_3":   false,
					"V1_1":   false,
				},
				Orderer: &Orderer{
					OrdererType:  "solo",
					Addresses:    []string{"orderer.example.com:7050"},
					BatchTimeout: 2 * time.Second,
					BatchSize: BatchSize{
						MaxMessageCount:   10,
						AbsoluteMaxBytes:  10 * 1024 * 1024,
						PreferredMaxBytes: 512 * 1024,
					},
					Organizations: []*Organization{
						{
							Name:   "OrdererOrg",
							ID:     "OrdererMSP",
							MSPDir: "crypto-config/ordererOrganizations/example.com/msp",
							Policies: map[string]*Policy{
								"Readers": {
									Type: "Signature",
									Rule: `OR('OrdererMSP.member')`,
								},
								"Writers": {
									Type: "Signature",
									Rule: `OR('OrdererMSP.member')`,
								},
								"Admins": {
									Type: "Signature",
									Rule: `OR('OrdererMSP.admin')`,
								},
							},
						},
					},
					Policies: map[string]*Policy{
						"Readers": {
							Type: "ImplicitMeta",
							Rule: "ANY Readers",
						},
						"Writers": {
							Type: "ImplicitMeta",
							Rule: "ANY Writers",
						},
						"Admins": {
							Type: "ImplicitMeta",
							Rule: "MAJORITY Admins",
						},
						"BlockValidation": {
							Type: "ImplicitMeta",
							Rule: "ANY Writers",
						},
					},
					Capabilities: map[string]bool{
						"V1_4_2": true,
						"V1_1":   false,
					},
				},
				Consortiums: map[string]*Consortium{
					"SampleConsortium": {
						Organizations: organizations,
					},
				},
			},
			"TwoOrgsChannel": {
				Consortium: "SampleConsortium",
				Policies: map[string]*Policy{
					"Readers": {
						Type: "ImplicitMeta",
						Rule: "ANY Readers",
					},
					"Writers": {
						Type: "ImplicitMeta",
						Rule: "ANY Writers",
					},
					"Admins": {
						Type: "ImplicitMeta",
						Rule: "MAJORITY Admins",
					},
				},
				Capabilities: map[string]bool{
					"V1_4_3": true,
					"V1_3":   false,
					"V1_1":   false,
				},
				Application: &Application{
					Policies: map[string]*Policy{
						"Readers": {
							Type: "ImplicitMeta",
							Rule: "ANY Readers",
						},
						"Writers": {
							Type: "ImplicitMeta",
							Rule: "ANY Writers",
						},
						"Admins": {
							Type: "ImplicitMeta",
							Rule: "MAJORITY Admins",
						},
					},
					Organizations: organizations,
					Capabilities: map[string]bool{
						"V1_4_2": true,
						"V1_3":   false,
						"V1_2":   false,
						"V1_1":   false,
					},
				},
			},
		},
	}
	data, err := yaml.Marshal(topLevel)
	if err != nil {
		log.Fatal(err)
	}
	if err := ioutil.WriteFile("configtx.yaml", data, os.ModePerm); err != nil {
		log.Fatal(err)
	}
}
