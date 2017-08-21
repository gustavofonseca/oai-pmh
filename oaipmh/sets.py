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


class SetsRegistry:
    """Representa o registro de conjuntos de registros disponíveis.

    :param static_defs: lista associativa que contém objetos ``Set`` e
    referências a suas funções ``view``.
    """
    def __init__(self, ds, static_defs):
        self.ds = ds
        self.static_defs = static_defs
        self.static_views = {s.setSpec: v for s, v in static_defs}

    def list(self):
        return get_sets_on_statics(self.static_defs)

    def get(self, name):
        pass

    def get_view(self, name):
        return self.static_views.get(name)


def get_sets_on_statics(statics):
    return (s for s, _ in statics)


def get_sets_on_journals(ds, offset, count):
    journals = ds.list_journals(offset, count)
    return (map_journal_to_set(j) for j in journals)


def map_journal_to_set(journal):
    return Set(setSpec=journal.lead_issn, setName=journal.title)


def get_view_for_journal_set(set_):
    from oaipmh.datastores import ArticleMetaFilteredView
    view = ArticleMetaFilteredView({'code_title': set_.lead_issn})
    return view

