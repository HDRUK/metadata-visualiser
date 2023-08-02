from pyvis.network import Network
from graphviz import Digraph
from networkx.drawing.nx_agraph import graphviz_layout
import networkx as nx
import json
import requests
import re
import matplotlib.pyplot as plt

class ModelMapper:

    def find_connectors(self,data,connectors,origin,parent=None):
        if isinstance(data,dict):
            for k,v in data.items():
                name = f"{parent}.{k}"
                self.find_connectors(v,connectors,origin,parent=name)
        elif isinstance(data,list):
            for v in data:
                self.find_connectors(v,connectors,origin,parent=parent)
        elif isinstance(data,str) and origin in data:
            for x in re.findall(f"{origin}\.[^/\s]+", data):
                connectors.append({
                    'from':x,
                    'to':parent
                })
        elif isinstance(data,str) and 'extra' in data:
            for x in re.findall(f"extra\.[^/\s]+", data):
                connectors.append({
                    'from':x,
                    'to':parent
                })
            
    def find_nodes(self,data,nodes,parent=None):
         for k,v in data.items():
             name = f'{parent}.{k}'

             label = k
             #if not isinstance(v,dict):
             #    label = f"{k}: *{type(v).__name__}"

             nodes.append(
                 {
                     'name':f'{parent}.{k}',
                     'label':label,
                     'parent':parent
                 }
             )
             if isinstance(v,list):
                 for item in v:
                     if isinstance(item,dict):
                         self.find_nodes(item,nodes,parent=name)
             elif isinstance(v,dict):
                 self.find_nodes(v,nodes,parent=name)
             else:
                 pass
             
    def update_values_with_keys(self,d,mapper, parent_key=''):
        updated_dict = {}
        for key, value in d.items():
            new_key = f"{parent_key}.{key}" if parent_key else key
            
            if isinstance(value, dict):
                updated_dict[key] = self.update_values_with_keys(value, mapper, new_key)
            elif isinstance(value, list):
                for i in range(len(value)):
                    if isinstance(value[i],dict):
                        updated_dict[key] = self.update_values_with_keys(value[i], mapper, new_key)
                    else:                  
                        updated_dict[key] = f"{new_key}" 
                        mapper[new_key] = value
                if len(value) == 0:
                    #updated_dict[key] = [f"{new_key}"]
                    #mapper[new_key] = value
                    pass
            else:
                updated_dict[key] = new_key
                mapper[new_key] = value
                
        return updated_dict
     
    def get_output_metadata(self,input_metadata,
                            input_name,
                            output_name,
                            extra=None,check_output=0):
        
        response = requests.post(f'http://localhost:3000/translate?from={input_name}&to={output_name}&check_input=0&check_output={check_output}',
                                 json={
                                     'metadata':input_metadata,
                                     'extra':extra
                                 })

        
        if response.status_code != 200:
            print (json.dumps(response.json(),indent=6))
            raise Exception('bad')
        return response.json()
    
    def get_nodes_and_connector(self,input_metadata,output_metadata,input_name,output_name,extra):
        inodes = []
        self.find_nodes(input_metadata,inodes,parent=input_name)
        self.find_nodes(extra,inodes,parent='extra')

        onodes = [] 
        self.find_nodes(output_metadata,onodes,parent=output_name)
        connectors = []

        self.find_connectors(output_metadata,connectors,input_name,parent=output_name) 
        
        return inodes,onodes,connectors

    def get_nx_graph(self,icolor='mediumvioletred',ocolor='lightblue'):
        nx_graph = nx.DiGraph()
        nx_graph.add_node(self.input_name,label=self.input_name,color=icolor)
        nx_graph.add_node('extra',label='extra',color=icolor)

        for node in self.inodes:
            nx_graph.add_node(node['name'],label=node['label'],color=icolor)
            nx_graph.add_edge(node['parent'],node['name'],weight=5,color=icolor,arrow=False)


        nx_graph.add_node(self.output_name,label=self.output_name,color=ocolor)
        for node in self.onodes:
            nx_graph.add_node(node['name'],label=node['label'],color=ocolor)
            nx_graph.add_edge(node['name'],node['parent'],weight=5,color=ocolor,arrowsize=0)

        for c in self.connectors:
            nx_graph.add_edge(c['from'],c['to'],color='black',weight=1)

        self.nx_graph = nx_graph
        return self.nx_graph
    
    def get_network(self,nx_graph=None,directed=True,**kwargs):
        if nx_graph == None:
            nx_graph = self.get_nx_graph()
        nt = Network(notebook=True,directed=directed,**kwargs)
        nt.from_nx(nx_graph)
        #nt.barnes_hut(spring_strength=0.5,spring_length=0.1)
        nt.show(f'{self.input_name}_{self.output_name}.html')
        return nt
    
    def get_dot(self,inodes,onodes,connectors,input_data_mapper,output_data_mapper,input_name,output_name):
        
        dot = Digraph(strict=True,format='png')
        dot.attr(rankdir=self.rankdir)

        
        all_mapped = [
            item[key]
             for item in connectors
            for key in ['from','to']
        ]
        
        parents = []
        missing_mapping = []
        with dot.subgraph(name='cluster_0') as idot,\
             dot.subgraph(name='cluster_1') as odot,\
             dot.subgraph(name='cluster_10') as cdot:

            idot.attr(style='filled', fillcolor='2', colorscheme='blues9', penwidth='0', label='Input Metadata')
            odot.attr(style='filled', fillcolor='2', colorscheme='oranges9', penwidth='0', label='Output Metadata')
            cdot.attr(penwidth='0',margin='200')
            
            idot.node(input_name,label=input_name,style='filled',color='white')
            idot.node('extra',label='extra',style='filled',color='white')
            
            for node in inodes:
                idot.node(node['name'],label=node['label'],style='filled',color='white')
                idot.edge(node['parent'],node['name'],style='dotted',arrowhead='none')
                
                if node['parent']:
                    parents.append(node['parent'])
                    
            odot.node(output_name,label=output_name,style='filled',color='white')
            for node in onodes:
                
                odot.node(node['name'],label=node['label'],style='filled',color='white')
                odot.edge(node['name'],node['parent'],style='dotted',arrowhead='none')
                if node['parent']:
                    parents.append(node['parent'])

            for i,c in enumerate(connectors):
                color = 'black'
                label = 'modified'
                connectors[i]['mod'] = None
                if c['from'] in input_data_mapper and c['to'] in output_data_mapper:
                    if input_data_mapper[c['from']] == output_data_mapper[c['to']]:
                        label=''
                    else:
                        t1 = type(input_data_mapper[c['from']]).__name__
                        t2 = type(output_data_mapper[c['to']]).__name__
                        label = f"{t1} --> {t2}"
                        connectors[i]['mod'] = label
                        color = 'red'
                        print (c['from']," --> ",c['to']," (",label,")")

                idot.edge(c['from'],c['to'],penwidth='2.0',label=label,color=color)


            for node in inodes:
                if not node['name'] in parents and not node['name'] in all_mapped:
                    idot.node(node['name'],label=node['label'],style='filled',color='pink')
                    missing_mapping.append(node['name'])
                    
            for node in onodes:
                if not node['name'] in parents and not node['name'] in all_mapped:
                    odot.node(node['name'],label=node['label'],style='filled',color='pink')

            dot.graph_attr['dpi'] = '45'
            return dot

    def __init__(self,input_metadata,input_name,output_name,render=True,extra=None):

        self.dot = None
        self.rankdir = 'LR'
        #get output metadata from the original input
        self.input_metadata = input_metadata
        self.input_name = input_name
        self.output_name = output_name
        self.render = render
        self.extra = extra
        
        self.output_metadata = self.get_output_metadata(
            self.input_metadata,
            self.input_name,
            self.output_name,
            extra=self.extra,
            check_output=1)
        
        self.output_data_mapper = {}
        self.output_metadata_with_keys = self.update_values_with_keys(self.output_metadata,
                                                                      self.output_data_mapper,
                                                                      self.output_name)
        
        self.input_data_mapper = {}
        self.input_metadata_with_keys = self.update_values_with_keys(self.input_metadata,
                                                                     self.input_data_mapper,
                                                                     self.input_name)

        self.extra_with_keys = self.update_values_with_keys(self.extra,
                                                            self.input_data_mapper,
                                                            'extra')

        self.output_metadata_with_input_keys = self.get_output_metadata(self.input_metadata_with_keys,
                                                                        self.input_name,
                                                                        self.output_name,
                                                                        extra=self.extra_with_keys)
        
        
        
        self.inodes,self.onodes,self.connectors = self.get_nodes_and_connector(
            self.input_metadata_with_keys,
            self.output_metadata_with_input_keys,
            self.input_name,
            self.output_name,
            self.extra)
        
        
        self.all_out_nodes = []
        self.find_nodes(self.output_metadata_with_keys,self.all_out_nodes,parent=self.output_name)
        
        

    def get_diagram(self,render=None):
        if not render:
            render = self.render
        
        self.dot = self.get_dot(self.inodes,
                      self.onodes,
                      self.connectors,
                      self.input_data_mapper,
                      self.output_data_mapper,
                      self.input_name,
                      self.output_name)
        
        if not self.render:
            return self.dot

        self.save_diagram()
    
    def save_diagram(self):
        self.dot.graph_attr['dpi'] = '200'
        self.dot.render(f'{self.input_name}_{self.output_name}', view=True)


if __name__ == "__main__":

    metadata_example = {
        "identifier": "449f81a1-9ab4-449d-ba26-5829a855379e",
        "version": "2.0.0",
        "revisions": [
            {
                "version": "2.0.0",
                "url": "https://api.service.nhs.uk/health-research-data-catalogue/datasetrevisions/449f81a1-9ab4-449d-ba26-5829a855379e"
            }
        ],
        "issued": "2021-06-17T15:17:27.327Z",
        "modified": "2023-03-23T16:49:34.606Z",
        "summary": {
            "title": "Medicines dispensed in Primary Care (NHSBSA data)",
            "abstract": "The Medicines Dispensed in Primary Care (NHSBSA) data comprises prescriptions for medicines that are dispensed or supplied by community pharmacists, appliance contractors and dispensing doctors in England.",
            "publisher": {
                "name": "NHS ENGLAND",
                "memberOf": "ALLIANCE",
                "contactPoint": "england.contactus@nhs.net",
                "identifier": "5f86cd34980f41c6f02261f4",
                "logo": "1",
                "description": "blahh",
                "accessRights": ["a"],
                "deliveryLeadTime": "OTHER",
                "accessService": "basfasgaskogas",
                "accessRequestCost": "free",
                "dataUseLimitation": ['as'],
                "dataUseRequirements": ["das"]
            },
            "contactPoint": "england.contactus@nhs.net",
            "keywords": [
                "DIGITRIALS, Prescribing, Medicines, Dispensing, NCS, National Core Study, Covid"
            ],
            "alternateIdentifiers": ["1234"],
            "doiName": "10.7189/jogh.13.01003"
        },
        "documentation": {
            "description": "Since July 2020 NHS Digital has established a collection of data from electronic and paper prescriptions submitted to the NHSBSA for reimbursement each month.\n\nThe data comprises prescriptions for medicines that are dispensed or supplied by community pharmacists, appliance contractors and dispensing doctors in England.\n\nThe data also includes:\n\nprescriptions submitted by prescribing doctors, for medicines personally administered in England prescriptions written in England and dispensed outside of England prescriptions written in Wales, Scotland, Northern Ireland, the Isle of Man, Jersey and Guernsey but dispensed in England\n\nData includes prescriptions issued by prescribers in:\n\ngeneral practice community clinics hospital clinics dentists community nursing services.\n\nThere are around 90 to 100 million rows of patient-level data in this collection per month. Each row represents each medicine or appliance on a prescription and includes personal data (for example NHS number) and special category data (data concerning health).\n\nTimescales for dissemination of agreed data can be found under 'Our Service Levels' at the following link: [https://digital.nhs.uk/services/data-access-request-service-dars/data-access-request-service-dars-process](https://digital.nhs.uk/services/data-access-request-service-dars/data-access-request-service-dars-process) [Standard response](https://web.www.healthdatagateway.org/dataset/f201b68f-d995-4a70-a9ee-aa3510232777)",
            "associatedMedia": [
                "https://digital.nhs.uk/data-and-information/data-tools-and-services/data-services/medicines-dispensed-in-primary-care-nhsbsa-data"
            ],
            "isPartOf": [
                "NOT APPLICABLE"
            ]
        },
        "coverage": {
            "followup": "UNKNOWN",
            "spatial": [
                "https://www.geonames.org/6269131/england.html"
            ],
            "physicalSampleAvailability": [
                "NOT AVAILABLE"
            ],
            "pathway": "Medicines in community settings",
            "typicalAgeRange": "0-150"
        },
        "provenance": {
            "temporal": {
                "timeLag": "1-2 MONTHS",
                "accrualPeriodicity": "MONTHLY",
                "startDate": "2015-04-01",
                "distributionReleaseDate": "2015-04-01",
                "endDate": "2015-04-01"
            },
            "origin": {
                "purpose": [
                    "ADMINISTRATIVE",
                    "CARE",
                    "OTHER"
                ],
                "source": [
                    "PAPER BASED",
                    "OTHER"
                ],
                "collectionSituation": [
                    "OTHER",
                    "PRIMARY CARE",
                    "COMMUNITY",
                    "PRIVATE",
                    "PHARMACY"
                ]
            }
        },
        "accessibility": {
            "formatAndStandards": {
                "language": [
                    "en"
                ],
                "vocabularyEncodingScheme": [
                    "DM+D",
                    "ODS"
                ],
                "format": [
                    "CSV",
                    "Text"
                ],
                "conformsTo": [
                    "LOCAL"
                ]
            },
            "usage": {
                "dataUseLimitation": [
                    "No Restriction"
                ],
                "resourceCreator": [
                    "NHS ENGLAND"
                ],
                "dataUseRequirements": [
                    "INSTITUTION SPECIFIC RESTRICTIONS",
                    "PROJECT SPECIFIC RESTRICTIONS",
                    "TIME LIMIT ON USE"
                ],
                "investigations": [
                    "https://digital.nhs.uk/services/data-access-request-service-dars/register-of-approved-data-releases"
                ],
                "isReferencedBy": ["2135"]
            },
            "access": {
                "dataController": "NHS England (NHSE)",
                "jurisdiction": [
                    "GB-ENG"
                ],
                "dataProcessor": "NHS England (NHSE)",
                "accessService": "Once your DARS application has been approved, data will be made available either by secure file transfer or through the Data Access Environment (DAE). \nSecure file transfer: https://digital.nhs.uk/services/transfer-data-securely \nDAE: https://digital.nhs.uk/services/data-access-environment-dae",
                "accessRights": [
                    "https://digital.nhs.uk/services/data-access-request-service-dars"
                ],
                "accessRequestCost": [
                    "https://digital.nhs.uk/services/data-access-request-service-dars/data-access-request-service-dars-charges"
                ],
                "deliveryLeadTime": "OTHER"
            }
        },
        "enrichmentAndLinkage": {
            "tools": [
                "https://digital.nhs.uk/data-and-information/data-tools-and-services/data-services/medicines-dispensed-in-primary-care-nhsbsa-data#reference-data"
            ],
            "qualifiedRelation": [
                "https://digital.nhs.uk/services/data-access-request-service-dars/register-of-approved-data-releases"
            ],
            "derivation": [
                "Data will be minimised as appropriate relative to the data access application"
            ]
        },
        "observations": [
            {
                "observedNode": "PERSONS",
                "measuredValue": 18824070,
                "disambiguatingDescription": "Unique patients that have submitted prescriptions in Oct 2020.",
                "observationDate": "2020-10-31",
                "measuredProperty": "Count"
            }
        ]
    }

    #get_diagram(data_example,"datasetv2","hdrukv211")
    #data_example = json.load(open("example_2_1_1.json"))
    #extra = {
    #    'pid':1234,
    #    'id':1235
    #}
    #mapper = ModelMapper(data_example,'hdrukv211','gdmv1',extra=extra,render=True)
    #mapper.get_diagram()

    #data_example = json.load(open("example_gdm1.json"))

    extra = {
        "structuralMetadata": [
            {
                "tableName": "All Available Fields",
                "tableDescription": "fuck off",
                "columnName": "All Available Fields",
                "columnDescription": "All Available Fields",
                "dataType": "String",
                "sensitive": False
            }
        ]
    }

    with open("example_datasetv2_smd.json","w") as f:
        data = {'metadata':metadata_example,'extra':extra}
        json.dump(data,f,indent=6)
    
    #data_example = json.load(open("example_mongodb.json"))

    #print (data_example["metadata"].keys())
    
    #mapper = ModelMapper(metadata_example,'datasetv2','hdrukv211',extra=extra,render=True)
    mapper = ModelMapper(metadata_example,'datasetv2','hdrukv211',extra=extra,render=True)
    mapper.get_diagram()
    #mapper.get_network()
