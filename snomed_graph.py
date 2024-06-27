import pandas as pd
import networkx as nx
from tqdm.notebook import tqdm
from itertools import groupby
import re
from itertools import pairwise
from typing import Generator, Dict, List, Tuple, Type, Set
import os
from datetime import datetime

    
class SnomedConceptDetails():
    """
    A class to represent the essential details of a SNOMED CT concept
    """

    def __init__(self, sctid: int, fsn: str, synonyms: List[str] = None) -> None:
        self.sctid = sctid
        self.fsn = fsn
        self.synonyms = synonyms

    def __repr__(self):
        return f"{self.sctid} | {self.fsn}"

    def __eq__(self, other):
        return self.sctid == other.sctid

    def __hash__(self):
        return int(self.sctid)

    @property
    def hierarchy(self) -> str:
        hierarchy_match = re.search(r'\(([^)]+)\)\s*$', self.fsn)
        if hierarchy_match:
            return hierarchy_match[0][1:-1]
        else:
            return ""

class SnomedRelationship():
    """
    A class to represent a SNOMED CT relationship
    """

    def __init__(self, src: SnomedConceptDetails, tgt: SnomedConceptDetails, group: int, type: str, type_id: str) -> None:
        self.src = src
        self.tgt = tgt
        self.group = group
        self.type = type
        self.type_id = type_id

    def __repr__(self):
        return f"[{self.src}] ---[{self.type}]---> [{self.tgt}]"


class SnomedRelationshipGroup():

    def __init__(self, group: int, relationships: List[SnomedRelationship]) -> None:
        self.group = group
        self.relationships = relationships

    def __repr__(self):
        return f"Group {self.group}\n\t" + "\n\t".join([str(r) for r in self.relationships])


class SnomedConcept():

    def __init__(self, concept_details, parents, children, inferred_relationship_groups) -> None:
        self.concept_details = concept_details
        self.inferred_relationship_groups = inferred_relationship_groups
        self.parents = parents
        self.children = children

    def __repr__(self):
        str_ = str(self.concept_details)
        str_ += f"\n\nSynonyms:\n{self.concept_details.synonyms}"
        str_ += "\n\nParents:\n"
        str_ += "\n".join([str(p) for p in self.parents])
        str_ += "\n\nChildren:\n"
        str_ += "\n".join([str(c) for c in self.children])
        str_ += "\n\nInferred Relationships:\n"
        str_ += "\n".join([str(rg) for rg in self.inferred_relationship_groups])
        return str_

    @property
    def sctid(self) -> int:
        return self.concept_details.sctid

    @property
    def fsn(self) -> str:
        return self.concept_details.fsn

    @property
    def synonyms(self) -> List[str]:
        return self.concept_details.synonyms      

    @property
    def hierarchy(self) -> str:
        return self.concept_details.hierarchy      


class SnomedGraph():
    """
    A class to represent a SNOMED CT release as a Graph, using NetworkX.

    Attributes
    ----------
    G : nx.DiGraph
        The underlying graph
    """   

    fsn_typeId = 900000000000003001
    is_a_relationship_typeId = 116680003
    root_concept_id = 138875005
    default_langcode = "en"

    def __init__(self, G: nx.DiGraph) -> None:
        """
        Create a new instance of SnomedGraph from a NetworkX DiGraph object
    
        Args:
            G: A DiGraph created using SnomedGraph.from_rf2() or SnomedGraph.from_serialized().
        Returns:
            self.
        """
        self.G = G
        print(self)

    def __repr__(self):
        return f"SNOMED graph has {self.G.number_of_nodes()} vertices and {self.G.number_of_edges()} edges"

    def __iter__(self):
        for sctid in self.G.nodes:
            yield self.get_concept_details(sctid)

    def __len__(self):
        return self.G.number_of_nodes()

    def __contains__(self, item):
        return item in self.G

    def get_children(self, sctid: int) -> List[SnomedConceptDetails]:
        return [
            r.src for r in self.__get_in_relationships(sctid) 
            if r.type_id == SnomedGraph.is_a_relationship_typeId
        ]

    def get_parents(self, sctid: int) -> List[SnomedConceptDetails]:
        return [
            r.tgt for r in self.__get_out_relationships(sctid) 
            if r.type_id == SnomedGraph.is_a_relationship_typeId
        ]

    def get_inferred_relationships(self, sctid: int) -> List[SnomedRelationshipGroup]:
        """
        Retrieve the inferred relationships for a concept.  
        (N.B. these exclude the "is a" relationships, which can be retrieved by the
        get_parents() function instead.)

        Args:
            sctid: A valid SNOMED Concept ID.
        Returns:
            A list of SnomedRelationshipGroup objects.
        """        
        inferred_relationships = [
            r for r in self.__get_out_relationships(sctid) 
            if r.type_id != SnomedGraph.is_a_relationship_typeId
        ]        
        key_ = lambda r: r.group
        inferred_relationships_grouped = groupby(
            sorted(inferred_relationships, key=key_), 
            key=key_
        )
        inferred_relationship_groups = [
            SnomedRelationshipGroup(g, list(r)) 
            for g,r in inferred_relationships_grouped
        ] 
        return inferred_relationship_groups

    def get_concept_details(self, sctid: int) -> SnomedConceptDetails:
        """
        Retrieve the basic details for a concept: SCTID, FSN and synonyms.

        Args:
            sctid: A valid SNOMED Concept ID.
        Returns:
            A SnomedConceptDetails object.
        """
        return SnomedConceptDetails(sctid=sctid, **self.G.nodes[sctid])
        
    def get_full_concept(self, sctid: int) -> SnomedConcept:
        """
        Retrieve all attributes for a given concept.
    
        Args:
            sctid: A valid SNOMED Concept ID.
        Returns:
            A SnomedConcept object.
        """
        concept_details = self.get_concept_details(sctid)
        parents = self.get_parents(sctid)
        children = self.get_children(sctid)
        inferred_relationship_groups = self.get_inferred_relationships(sctid)
        return SnomedConcept(concept_details, parents, children, inferred_relationship_groups)
        
    def __get_out_relationships(self, src_sctid: int) -> Generator[Dict, None, None]:
        src = SnomedConceptDetails(sctid=src_sctid, **self.G.nodes[src_sctid])
        for _, tgt_sctid in self.G.out_edges(src_sctid):
            tgt = SnomedConceptDetails(sctid=tgt_sctid, **self.G.nodes[tgt_sctid])
            vals = self.G.edges[(src_sctid, tgt_sctid)]
            yield SnomedRelationship(src, tgt, **vals)

    def __get_in_relationships(self, tgt_sctid: int) -> Generator[Dict, None, None]:
        tgt = SnomedConceptDetails(sctid=tgt_sctid, **self.G.nodes[tgt_sctid])
        for src_sctid, _ in self.G.in_edges(tgt_sctid):
            src = SnomedConceptDetails(sctid=src_sctid, **self.G.nodes[src_sctid])
            vals = self.G.edges[(src_sctid, tgt_sctid)]
            yield SnomedRelationship(src, tgt, **vals) 

    def get_descendants(self, sctid: int, steps_removed: int = None) -> List[SnomedConceptDetails]:
        """
        Retrieve descendants of a given concept.
    
        Args:
            sctid: A valid SNOMED Concept ID.
            steps_removed: The number of levels down in the hierarchy to go.  
                           (1 => children; 2 => children + grandchildren, etc)
                           if None then all children are retrieved.
        Returns:
            A list containing the SCTIDs of all descendants.
        """
        if steps_removed is None:
            steps_removed = 99999
        elif steps_removed <= 0:
            raise AssertionError("steps_removed must be > 0 or None")
        children = self.get_children(sctid)
        descendants = set(children)
        if steps_removed > 1:
            for c in children:
                descendants = descendants.union(
                    self.get_descendants(c.sctid, steps_removed-1)
                )
        return descendants

    def get_ancestors(self, sctid: int, steps_removed: int = None) -> List[SnomedConceptDetails]:
        """
        Retrieve ancestors of a given concept.
    
        Args:
            sctid: A valid SNOMED Concept ID.
            steps_removed: The number of levels up in the hierarchy to go.  
                           (1 => parents; 2 => parents + grandparents, etc)
                           if None then all parents are retrieved.
        Returns:
            A list containing the SCTIDs of all descendants.
        """        
        if steps_removed is None:
            steps_removed = 99999
        elif steps_removed <= 0:
            raise AssertionError("steps_removed must be > 0 or None")
        parents = self.get_parents(sctid)
        ancestors = set(parents)
        if steps_removed > 1:
            for p in parents:
                ancestors = ancestors.union(
                    self.get_ancestors(p.sctid, steps_removed-1)
                )
        return set([a for a in ancestors if not a.sctid == SnomedGraph.root_concept_id])

    def get_neighbourhood(self, sctid: int, steps_removed: int = 1) -> List[SnomedConceptDetails]:
        """
        Retrieve neighbours of a given concept.
        Neighbours include ancestors, descendants and cousins up to the given degree.
    
        Args:
            sctid: A valid SNOMED Concept ID.
            steps_removed: The number of steps up or down in the hierarchy to go.
                           Defaults to 1 (parents + children).
        Returns:
            A list containing the SCTIDs of all neighbours.
        """            
        assert steps_removed > 0
        parents = self.get_parents(sctid)
        children = self.get_children(sctid)
        neighbourhood = set(parents).union(children)
        if steps_removed > 1:
            for n in list(neighbourhood):
                neighbourhood = neighbourhood.union(
                    self.get_neighbourhood(n.sctid, steps_removed-1)
                )
        neighbourhood = [
            n for n in neighbourhood
            if n.sctid not in [sctid, SnomedGraph.root_concept_id]
        ]
        return neighbourhood
    
    def find_path(self, sctid1: int, sctid2: int, print_: bool = False) -> List[SnomedRelationship]:
        """
        Returns details of the shortest path that exists between two concepts.
        The path considers all relationship types but limits the results to true ancestors
        or descentants - i.e. concepts that are "cousins" of one another will not result in
        a returned path.
    
        Args:
            sctid1: A valid SNOMED Concept ID.
            sctid2: A valid SNOMED Concept ID.
            print_: Whether to print the full path as a string.
        Returns:
            A list of Relationships of the form (source, relationship_type, target).
            These are the steps of the shortest path from source to target.
        """         
        path = []
        if nx.has_path(self.G, sctid1, sctid2):
            nodes = nx.shortest_path(self.G, sctid1, sctid2)
        elif nx.has_path(self.G, sctid2, sctid1):
            nodes = nx.shortest_path(self.G, sctid2, sctid1)
        else:
            nodes = []
        for src_sctid, tgt_sctid in pairwise(nodes):
            vals = self.G.edges[(src_sctid, tgt_sctid)]
            src = SnomedConceptDetails(sctid=src_sctid, **self.G.nodes[src_sctid])
            tgt = SnomedConceptDetails(sctid=tgt_sctid, **self.G.nodes[tgt_sctid])
            relationship = SnomedRelationship(src, tgt, **vals)
            path.append(relationship)
        if print_:
            if len(nodes) > 0:
                str_ = f"[{path[0].src}]"
                for r in path:
                    str_ += f" ---[{r.type}]---> [{r.tgt}]"
                print(str_)
            else:
                print("No path found.")
        return path

    def path_to_root(self, sctid: int, print_: bool = False) -> List[SnomedRelationship]:
        """
        Finds the shortest "Is A" path from the concept to the Root concept.
        Can be used to find the "depth" of a concept.
        
        Args:
            sctid: A valid SNOMED Concept ID.
            print_: Whether to print the full path as a string.
        Returns:
            A list of Relationships of the form (source, relationship_type, target).
            These are the steps of the shortest path from the concept to the root.
        """
        shortest_path = None
        for nodes in nx.all_simple_paths(self.G, sctid, self.root_concept_id):
            path = list()
            for src_sctid, tgt_sctid in pairwise(nodes):
                vals = self.G.edges[(src_sctid, tgt_sctid)]
                src = SnomedConceptDetails(sctid=src_sctid, **self.G.nodes[src_sctid])
                tgt = SnomedConceptDetails(sctid=tgt_sctid, **self.G.nodes[tgt_sctid])
                relationship = SnomedRelationship(src, tgt, **vals)
                if relationship.type_id == self.is_a_relationship_typeId:
                    path.append(relationship)
                else:
                    path = None
                    break
            if path:
                if shortest_path:
                    if len(shortest_path) > len(path):
                        shortest_path = path
                else:
                    shortest_path = path
        if print_:
            str_ = f"[{shortest_path[0].src}]"
            for r in shortest_path:
                str_ += f" ---[{r.type}]---> [{r.tgt}]"
            print(str_)
        return shortest_path

    def save(self, path: str) -> None:
        """
        Save this SnomedGraph
    
        Args:
            path: path + name of the file to save to.
        Returns:
            None
        """          
        nx.write_gml(self.G, path)

    def to_pandas(self) -> Tuple[pd.DataFrame, pd.DataFrame]:
        """
        Fetch node and edge CSVs for this graph
    
        Args:
            None
        Returns:
            Two CSVs (nodes, edges) as Pandas DataFrames
        """
        nodes_df = (
            pd.DataFrame([{"sctid": n, **self.G.nodes[n]} for n in self.G.nodes])
            .set_index("sctid")
        )
        edges_df = nx.to_pandas_edgelist(self.G)
        return nodes_df, edges_df

    @property
    def relationship_types(self) -> Set[str]:
        """
        Fetch the set of all extant relationship types that exist.
    
        Args:
            None
        Returns:
            A Set of strings
        """
        return set(nx.get_edge_attributes(self.G, "type").values())

    @staticmethod
    def from_serialized(path: str):
        """
        Load a SnomedGraph from a serialization.
    
        Args:
            path: path + name of the file to save to.
        Returns:
            A SnomedGraph
        """            
        G = nx.read_gml(path, destringizer=int)
        return SnomedGraph(G)    

    @staticmethod
    def get_core_file_paths(path: str, langcode: str = "en"):
        if not os.path.exists(path):
            raise AssertionError(f'The path "{path}" does not exist')
        base_dir = os.path.dirname(path)
        dir = os.path.basename(path)
        try:
            elements = dir.split("_")
            assert len(elements) in [4, 5]
            if len(elements) == 5:
                filetype, contenttype, contentsubtype, countrynamespace, versiondate = elements
            else:
                filetype, contenttype, contentsubtype, versiondate = elements
                countrynamespace = "INT"
            versiondate = datetime.strptime(versiondate, "%Y%m%dT%H%M%SZ").strftime("%Y%m%d")
        except (AttributeError, ValueError, AssertionError):
            raise AssertionError(
                f' The specified folder "{dir}" does not appear to follow the SNOMED CT Release Format naming convention.'
            )
        else:
            relationships_path = f"{base_dir}/{dir}/Snapshot/Terminology/sct2_Relationship_Snapshot_{countrynamespace}_{versiondate}.txt"
            if not os.path.exists(relationships_path):
                raise AssertionError(f'The path "{relationships_path}" does not exist')
            descriptions_path = f"{base_dir}/{dir}/Snapshot/Terminology/sct2_Description_Snapshot-{langcode}_{countrynamespace}_{versiondate}.txt"
            if not os.path.exists(descriptions_path):
                raise AssertionError(f'The path "{descriptions_path}" does not exist')            
        return relationships_path, descriptions_path

    # def load_national_extension(self, path: str, langcode: str):
    #     relationships_path, descriptions_path = SnomedGraph.get_core_file_paths(path, langcode)
        
    #     # Load relationships
    #     relationships_df = pd.read_csv(relationships_path, delimiter="\t")
    #     relationships_df = relationships_df[relationships_df.active == 1]
        
    #     # Load concepts
    #     concepts_df = pd.read_csv(descriptions_path, delimiter="\t")
    #     concepts_df = concepts_df[concepts_df.active == 1]
    #     concepts_df.set_index("conceptId", inplace=True)

    #     n_concepts = concepts_df.shape[0]
    #     n_relationships = relationships_df.shape[0]
    #     print(f"{n_concepts} terms and {n_relationships} relationships were found in the extension.")        

    #     # Add concepts            
    #     print("Adding Concepts...")
    #     for sctid, rows in tqdm(concepts_df.groupby(concepts_df.index)):
    #         synonyms = [row.term for _, row in rows.iterrows() if row.typeId != SnomedGraph.fsn_typeId]
    #         try:
    #             fsn = rows[rows.typeId == SnomedGraph.fsn_typeId].term.values[0]
    #         except IndexError:
    #             fsn = None
    #         translations = {"fsn": fsn, "synonyms": synonyms}
    #         self.G.add_node(sctid, langcode=translations)
        
    
    @staticmethod
    def from_rf2(path: str):
        """
        Create a SnomedGraph from a SNOMED RF2 release path.
    
        Args:
            path: Path to RF2 release folder.
        Returns:
            A SnomedGraph
        """          
        relationships_path, descriptions_path = SnomedGraph.get_core_file_paths(path)
        
        # Load relationships
        relationships_df = pd.read_csv(relationships_path, delimiter="\t")
        relationships_df = relationships_df[relationships_df.active == 1]
        
        # Load concepts
        concepts_df = pd.read_csv(descriptions_path, delimiter="\t")
        concepts_df = concepts_df[concepts_df.active == 1]
        concepts_df.set_index("conceptId", inplace=True)

        # Create relationships type lookup
        relationship_types = concepts_df.loc[relationships_df.typeId.unique()]
        relationship_types = relationship_types[relationship_types.typeId == SnomedGraph.fsn_typeId]
        relationship_types = relationship_types.term.to_dict()

        # Initialise the graph
        n_concepts = concepts_df.shape[0]
        n_relationships = relationships_df.shape[0]
        print(f"{n_concepts} terms and {n_relationships} relationships were found in the release.")
        G = nx.DiGraph()            

        # Create relationships
        print("Creating Relationships...")
        for r in tqdm(relationships_df.to_dict(orient="records")):
            G.add_edge(        
                r["sourceId"], 
                r["destinationId"], 
                group=r["relationshipGroup"], 
                type=relationship_types[r["typeId"]],
                type_id=r["typeId"]
            )

        # Add concepts            
        print("Adding Concepts...")
        for sctid, rows in tqdm(concepts_df.groupby(concepts_df.index)):
            synonyms = [row.term for _, row in rows.iterrows() if row.typeId != SnomedGraph.fsn_typeId]
            try:
                fsn = rows[rows.typeId == SnomedGraph.fsn_typeId].term.values[0]
            except IndexError:
                fsn = synonyms[0]
                synonyms = synonyms[1:]
                print(f"Concept with SCTID {sctid} has no FSN. Using synonym '{fsn}' instead.")
            G.add_node(sctid, fsn=fsn, synonyms=synonyms)

        # Remove isolates
        G.remove_nodes_from(list(nx.isolates(G)))
        
        # Initialise class            
        return SnomedGraph(G)
