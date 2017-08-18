"""
Deve ser possível:
  * Estruturar os conjuntos de forma hierárquica;
  * Acrescentar novos conjuntos sem que haja refatoração; Design para extensão;
  * Representar conjuntos dinâmicos (aqueles que podem ser acrescentados
    durante a execução do programa como resultado da inclusão de novos registros.
    São conjuntos que agrupam registros pelo valor de determinado atributo.
    e.g.: ISSN, tipo de documento, ano de publicação etc);
  * Representar conjuntos estáticos (definidos no momento da compilação pelo
    programador);
  * Listar os diversos conjuntos disponibilizados pelo repositório;
  * Sinalizar nos registros os conjuntos os quais estão contidos;
  * Consultar os registros contidos em um conjunto;
  
"""
from collections import namedtuple, OrderedDict


Set = namedtuple('Set', '''setSpec setName''')


#SETS_REGISTRY = OrderedDict([
#    ('0100-879X', {'meta': Set(setSpec='0100-879X', setName='Brazilian Journal of Medical and Biological Research', setDescription=''), 'view': lambda x: x}),
#    ])

def get_sets_on_journals(ds, offset, count):
    journals = ds.list_journals(offset, count)
    return map_journals_to_sets(journals)


def map_journals_to_sets(journals):
    return (Set(setSpec=j.lead_issn, setName=j.title) for j in journals) 


def get_view_for_journal_set(set_):
    from oaipmh.datastores import ArticleMetaFilteredView
    view = ArticleMetaFilteredView({'code_title': set_.lead_issn})
    return view

