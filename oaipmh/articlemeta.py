from collections import (
        namedtuple,
        OrderedDict,
        )
import datetime
import functools
import itertools
import json
import logging

from articlemeta import client as articlemeta_client

from . import utils
from .datastores import (
        DataStore,
        DoesNotExistError,
        identityview,
        )
from .sets import SetsRegistry
from .entities import (
        Resource,
        Set,
        )


LOGGER = logging.getLogger(__name__)


Journal = namedtuple('Journal', '''title lead_issn''')
        

class SliceableResultSetThriftClient(articlemeta_client.ThriftClient):
    """Altera o comportamento do método ``documents`` para que seja possível
    controlar os argumentos ``limit`` e ``offset`` na consulta ao backend.
    """
    def __documents_ids(self, collection=None, issn=None, from_date=None,
            until_date=None, extra_filter=None, limit=None, offset=None):
        limit = limit or articlemeta_client.LIMIT
        offset = offset or 0
        from_date = from_date or articlemeta_client.DEFAULT_FROM_DATE
        until_date = until_date or datetime.datetime.today().isoformat()[:10]

        try:
            LOGGER.debug('querying ArticleMeta backend using params'
                         ' "collection=%s", "issn=%s", "from_date=%s",'
                         ' "until_date=%s", "limit=%s", "offset=%s",'
                         ' "extra_filter=%s"', collection, issn, from_date,
                         until_date, limit, offset, extra_filter)

            identifiers = self.dispatcher('get_article_identifiers',
                    collection=collection, issn=issn,
                    from_date=from_date, until_date=until_date,
                    limit=limit, offset=offset,
                    extra_filter=extra_filter)
        except self.ARTICLEMETA_THRIFT.ServerError:
            msg = 'Error retrieving list of article identifiers: %s_%s' % (collection, issn)
            raise articlemeta_client.ServerError(msg)

        if len(identifiers) == 0:
            return

        for identifier in identifiers:
            yield identifier


    def documents(self, collection=None, issn=None, from_date=None,
                  until_date=None, fmt='xylose', body=False, extra_filter=None,
                  only_identifiers=False, limit=None, offset=None):
        identifiers = self.__documents_ids(collection=collection, issn=issn,
                from_date=from_date, until_date=until_date,
                extra_filter=extra_filter, limit=limit, offset=offset)
        for identifier in identifiers:
            if only_identifiers:
                yield identifier
            else:
                document = self.document(
                    identifier.code,
                    identifier.collection,
                    replace_journal_metadata=False,
                    fmt=fmt,
                    body=body
                )
                yield document

    def __journals_ids(self, collection=None, issn=None, limit=None,
            offset=None):
        limit = limit or articlemeta_client.LIMIT
        offset = offset or 0

        try:
            with self.client_context() as client:
                identifiers = client.get_journal_identifiers(
                    collection=collection, issn=issn,
                    limit=limit, offset=offset)
        except self.ARTICLEMETA_THRIFT.ServerError:
            msg = 'Error retrieving list of journals identifiers: %s_%s' % (collection, issn)
            raise articlemeta_client.ServerError(msg)

        if len(identifiers) == 0:
            return

        for identifier in identifiers:
            yield identifier

    def journals(self, collection=None, issn=None, only_identifiers=False,
            limit=None, offset=None):
        identifiers = self.__journals_ids(collection=collection, issn=issn,
                limit=limit, offset=offset)
        for identifier in identifiers:
            if only_identifiers:
                yield identifier
            else:
                journal = self.journal(
                    identifier.code,
                    identifier.collection,
                )
                yield journal


class BoundArticleMetaClient:
    """Cliente da API ArticleMeta cujas consultas são vinculadas ao conteúdo
    de determinada coleção.
    """
    def __init__(self, client, collection):
        self.client = client
        self.collection = collection

    def document(self, code):
        return self.client.document(code, self.collection)

    def documents(self, issn=None, from_date=None, until_date=None,
            offset=0, limit=1000, extra_filter=None):
        return self.client.documents(collection=self.collection, issn=issn,
                from_date=from_date, until_date=until_date, offset=offset,
                limit=limit, extra_filter=extra_filter)

    def journals(self, issn=None, only_identifiers=False, limit=None,
            offset=None):
        return self.client.journals(collection=self.collection, issn=issn,
                only_identifiers=only_identifiers, offset=offset, limit=limit)

    def journal(self, code):
        return self.client.journal(code, self.collection)


def get_articlemeta_client(collection, **kwargs):
    """Retorna um cliente do serviço ArticleMeta otimizado e adaptado para
    uso como DataStore.
    """
    thriftclient = SliceableResultSetThriftClient(**kwargs)
    adaptedclient = BoundArticleMetaClient(thriftclient, collection)
    return adaptedclient


class ResourceRIdCodec:
    def encode(self, ridentifier):
        return 'oai:scielo:%s' % ridentifier

    def decode(self, ridentifier):
        return ridentifier.replace('oai:scielo:', '')


class ArticleResourceFacade:
    def __init__(self, article, rid_codec=None):
        self.article = article
        self.rid_codec = rid_codec or ResourceRIdCodec()

    def ridentifier(self):
        return self.rid_codec.encode(self.article.publisher_id)

    def datestamp(self):
        return utils.parse_date(self.article.processing_date)

    def setspec(self):
        return [self.article.any_issn()]

    def _translated_titles(self):
        transtitles = self.article.translated_titles()
        return transtitles or {}

    def title(self):
        art = self.article
        titles = [(art.original_language(), art.original_title())]

        translated_titles = self._translated_titles()
        if translated_titles:
            titles += translated_titles.items()
        return titles

    def _authors(self):
        authors = self.article.authors
        return authors or {}

    def creator(self):
        return [', '.join([author.get('surname', ''), author.get('given_names', '')])
                for author in self._authors()]

    def subject(self):
        subjects = []

        keywords = self.article.keywords()
        if keywords:
            for lang, kwds in keywords.items():
                for kwd in kwds:
                    subjects.append((lang, kwd))

        return subjects

    def description(self):
        art = self.article
        abstracts = [(art.original_language(), art.original_abstract())]

        translated_abstracts = art.translated_abstracts()
        if translated_abstracts:
            abstracts += translated_abstracts.items()

        return abstracts

    def publisher(self):
        return self.article.journal.publisher_name

    def contributor(self):
        return []

    def date(self):
        pubdate = utils.parse_date(self.article.publication_date)
        return [pubdate]

    def type(self):
        typ = self.article.document_type
        return [typ]

    def format(self):
        return ['text/html']

    def identifier(self):
        html_url = self.article.html_url()
        return [html_url]

    def _bibliographic_legends(self):
        biblegends = self.article.bibliographic_legends()
        return biblegends or {}

    def source(self):
        """Algo tipo: ['Revista de Microbiologia v.29 n.3 1998']
        """
        return [self._bibliographic_legends().get('descriptive_format')]

    def language(self):
        lang = self.article.original_language()
        return [lang]

    def relation(self):
        return []

    def _permissions(self):
        perms = self.article.permissions
        return perms or {}

    def rights(self):
        license_url = self._permissions().get('url', '')
        return [license_url]

    def to_resource(self):
        return Resource(ridentifier=self.ridentifier(),
                        datestamp=self.datestamp(),
                        setspec=self.setspec(),
                        title=self.title(),
                        creator=self.creator(),
                        subject=self.subject(),
                        description=self.description(),
                        publisher=self.publisher(),
                        contributor=self.contributor(),
                        date=self.date(),
                        type=self.type(),
                        format=self.format(),
                        identifier=self.identifier(),
                        source=self.source(),
                        language=self.language(),
                        relation=self.relation(),
                        rights=self.rights())


def journal_from_articlemeta(journal):
    """Produz uma instância de ``Journal`` com base em ``journal``.

    :param journal: instância de ``xylose.scielodocument.Journal``.
    """
    return Journal(title=journal.title,
                   lead_issn=journal.scielo_issn)


def is_spurious_doc(doc):
    """Instâncias de ``xylose.scielodocument.Article`` são produzidas pelo
    articlemetaapi mesmo para consultas a documentos que não existem.
    """
    try:
        doc.original_language()
    except TypeError:
        return True
    else:
        return False


class ArticleMetaFilteredView:
    """Um conjunto de resultados de uma consulta prévia aos registros. Algo
    similar ao conceito de View em SGBDs relacionais.

    >>> bmj = datastores.ArticleMetaFilteredView({"code_title": "0001-3714"})
    >>> [doc.ridentifier for doc in client.list(view=bmj)]
    """
    def __init__(self, term):
        self.term = json.dumps(dict(term))

    def __call__(self, query_fn):
        return functools.partial(query_fn, extra_filter=self.term)


class ArticleMeta(DataStore):
    """Adapta ``client`` para a interface de ``DataStore``.
    """
    def __init__(self, client: BoundArticleMetaClient, rid_codec=None):
        self.client = client
        self.rid_codec = rid_codec or ResourceRIdCodec()

    def add(self, resource):
        return NotImplemented

    def get(self, ridentifier):
        decoded_rid = self.rid_codec.decode(ridentifier)
        doc = self.client.document(decoded_rid)
        if is_spurious_doc(doc):
            raise DoesNotExistError()
        return ArticleResourceFacade(doc, self.rid_codec).to_resource()

    def list(self, offset, count, view=None, _from=None, until=None):
        view_fn = view or identityview
        query_fn = view_fn(self.client.documents)

        docs = query_fn(offset=offset, limit=count,
                from_date=_from, until_date=until)
        return (ArticleResourceFacade(doc, self.rid_codec).to_resource()
                for doc in docs)

    def get_journal(self, issn):
        journal = self.client.journal(issn)
        if journal is None:
            raise DoesNotExistError()
        return journal_from_articlemeta(journal)

    def list_journals(self, offset=0, count=1000):
        journals = self.client.journals(offset=offset, limit=count)
        return (journal_from_articlemeta(j) for j in journals)


class ArticleMetaSetsRegistry(SetsRegistry):
    """Implementa ``SetsRegistry`` com "sets virtuais" baseados em registros
    e estratégias de consulta ao ``DataStore``.

    :param datastore: instância de ``oaipmh.datastores.DataStore``.
    """
    def __init__(self, datastore, **kwargs):
        self.ds = datastore
        self.sets = OrderedDict()

    def add(self, metadata, view):
        self.sets[metadata.setSpec] = (metadata, view)

    def list(self, offset, count):
        static_part = [meta for meta, _ in self.sets.values()][offset:offset+count]
        if len(static_part) < count:
            dynamic_part = get_sets_from_journals(self.ds,
                    translate_virtual_offset(len(self.sets), offset),
                    count - len(static_part))
        else:
            dynamic_part = []

        return itertools.chain(static_part, dynamic_part)

    def get_view(self, setspec):
        try:
            _, view = self.sets[setspec]
        except KeyError:
            try:
                return get_view_for_journal_set(get_set_from_journal(self.ds,
                    setspec))
            except DoesNotExistError:
                return None

        return view


def translate_virtual_offset(size, offset):
    """Despreza o intervalo ``size`` em ``offset`` correspondente aos sets
    estáticos, retornando um novo ``offset`` que pode ser utilizado na consulta
    aos sets dinâmicos.
    """
    real_offset = offset - size 
    if real_offset <= 0:
        return 0
    else:
        return real_offset


def get_sets_from_journals(ds, offset, count):
    """Sequência de ``Set`` à partir de periódicos da fonte de dados ``ds``.
    """
    journals = ds.list_journals(offset, count)
    return (map_journal_to_set(j) for j in journals)


def get_set_from_journal(ds, issn):
    """``Set`` à partir de periódico da fonte de dados ``ds``.
    """
    journal = ds.get_journal(issn)
    return map_journal_to_set(journal)


def map_journal_to_set(journal):
    """``Set`` à partir de ``oaipmh.datastores.Journal``.
    """
    return Set(setSpec=journal.lead_issn, setName=journal.title)


def get_view_for_journal_set(set_):
    """Obtém uma função ``view`` que aplica filtro por registros do periódico
    representado por ``set_``.
    """
    view = ArticleMetaFilteredView({'code_title': set_.setSpec})
    return view

