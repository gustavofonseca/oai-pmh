import re
from collections import namedtuple
from datetime import datetime
from typing import (
        Type,
        TypeVar,
        Iterable,
        )

from . import exceptions


# serve apenas para type-hinting:
TResumptionToken = TypeVar('TResumptionToken', bound='ResumptionToken')


RepositoryMeta = namedtuple('RepositoryMeta', '''repositoryName baseURL
        protocolVersion adminEmail earliestDatestamp deletedRecord
        granularity''')


OAIRequest = namedtuple('OAIRequest', '''verb identifier metadataPrefix set
        resumptionToken from_ until''')


MetadataFormat = namedtuple('MetadataFormat', '''metadataPrefix schema
        metadataNamespace''')


"""
Representa um objeto de informação.

É inspirado no modelo de dados Dublin Core conforme definido originalmente em
[RFC2413]. Com exceção de ``repoidentifier`` e ``datestamp``, todos os atributos
são multivalorados, e alguns são listas associativas.
http://dublincore.org/documents/1999/07/02/dces/

sample = {
    'ridentifier': <str>,
    'datestamp': <datetime>,
    'setspec': <List[str]>,
    'title': <List[Tuple[str, str]]>,
    'creator': <List[str]>,
    'subject': <List[Tuple[str, str]]>,
    'description': <List[Tuple[str, str]]>,
    'publisher': <List[str]>,
    'contributor': <List[str]>,
    'date': <List[datetime]>,
    'type': <List[str]>,
    'format': <List[str]>,
    'identifier': <List[str]>,
    'source': <List[str]>,
    'language': <List[str]>,
    'relation': <List[str]>,
    'rights': <List[str]>,
},
res = Resource(**sample)
"""
Resource = namedtuple('Resource', '''ridentifier datestamp setspec title
        creator subject description publisher contributor date type format
        identifier source language relation rights''')


Set = namedtuple('Set', '''setSpec setName''')


class ResumptionToken:
    """Representa uma consulta que produz um conjunto de resultados e a posição
    do cursor dentro desse conjunto de resultados.

    O atributo de classe ``attrs`` contém a lista de dados codificados pelo token.
    
    É importante notar que essa classe é acoplada ao DataStore subjacente,
    principalmente por conta da lógica de paginação. Por esse motivo, deve-se
    utilizar os métodos prefixados com ``query_`` nas consultas aos dados.
    """
    attrs = ['set', 'from_', 'until', 'offset', 'count', 'metadataPrefix']
    token_patterns = {
            'ListRecords': r'^(\w+)?:((\d{4})-(\d{2})-(\d{2}))?:((\d{4})-(\d{2})-(\d{2}))?:(\d{4})-(\d{2})-(\d{2})\(\d+\):\d+:\w+$',
            'ListIdentifiers': r'^(\w+)?:((\d{4})-(\d{2})-(\d{2}))?:((\d{4})-(\d{2})-(\d{2}))?:\d+:\d+:\w+$',
            'ListSets': r'^:((\d{4})-(\d{2})-(\d{2}))?:((\d{4})-(\d{2})-(\d{2}))?:\d+:\d+:$',
            }

    def __init__(self, **kwargs):
        for attr in self.attrs:
            setattr(self, attr, kwargs.get(attr, None))

    @classmethod
    def new_from_request(cls: Type[TResumptionToken], oairequest: OAIRequest,
            default_count: int, default_from: str, default_until: str) -> TResumptionToken:
        """Obtém um ``ResumptionToken`` à partir do ``oairequest``.

        Caso o token não seja válido sintaticamente ou o valor do atributo ``count``
        seja diferente de ``default_count``, levanta a exceção ``BadResumptionToken``;
        Retorna um novo ``ResumptionToken`` caso não haja um codificado no
        ``oairequest``.
        """
        if oairequest.resumptionToken:
            if not cls._is_valid_oairequest(oairequest):
                raise exceptions.BadResumptionTokenError()

            token = cls.decode(oairequest.resumptionToken)
            if int(token.count) != default_count:
                raise exceptions.BadResumptionTokenError('token count is different than ``oaipmh.listslen``')
        else:
            token = cls(set=oairequest.set,
                        from_=oairequest.from_ or default_from,
                        until=oairequest.until or default_until,
                        offset='%s(0)' % (oairequest.from_ or default_from),
                        count=str(default_count),
                        metadataPrefix=oairequest.metadataPrefix)

        return token

    def is_first_page(self):
        """Retorna ``True`` caso ``self`` seja referente a primeira página de
        resultados de uma consulta."""
        return self.offset == ('%s(0)' % self.from_)

    def _lower_limit(self):
        return self.from_

    def _upper_limit(self):
        return self.until

    def query_offset(self):
        """Tamanho do offset a ser usado na consulta."""
        skip = slice(self.offset.index('(') + 1, -1)
        return int(self.offset[skip])

    def query_from(self):
        """Data inicial a ser usada na consulta."""
        date = slice(0, 10)
        return self.offset[date]

    def query_until(self):
        """Data final a ser usada na consulta."""
        year = slice(0, 4)
        ref_date = self.query_from()
        until = ref_date[year] + '-12-31'
        if self._upper_limit() <= until:
            return self._upper_limit()
        else:
            return until

    def query_count(self):
        """Quantidade de itens a serem retornados na consulta."""
        return int(self.count)

    @classmethod
    def decode(cls: Type[TResumptionToken], token: str) -> TResumptionToken:
        """Retorna uma instância de ``cls`` à partir da sua forma
        codificada."""
        keys = cls.attrs
        values = token.split(':')
        kwargs = dict(zip(keys, values))
        return cls(**kwargs)

    @classmethod
    def _is_valid_token(cls: Type[TResumptionToken], token: str,
            pattern: str) -> bool:
        """Se o valor de ``token`` é válido sintaticamente.
        """
        return bool(re.fullmatch(pattern, token))

    @classmethod
    def _get_validation_pattern(cls, verb: str) -> str:
        try:
            return cls.token_patterns[verb]
        except KeyError:
            raise ValueError() from None

    @classmethod
    def _is_valid_oairequest(cls: Type[TResumptionToken],
            oairequest: OAIRequest) -> bool:
        pattern = cls._get_validation_pattern(oairequest.verb)
        return cls._is_valid_token(oairequest.resumptionToken,
                pattern)

    def encode(self) -> str:
        """Codifica o token em string delimitada por ``:``.

        Durante a codificação, todos os valores serão transformados em ``str``.
        ``None`` será transformado em string vazia. 

        É importante ter em mente que o processo de codificação faz com que os
        tipos originais dos valores sejam perdidos, i.e., não é um processo
        reversível.
        """
        def ensure_str(obj):
            if obj is None:
                return ''
            else:
                try:
                    return str(obj)
                except:
                    return ''
        token = [getattr(self, attr) for attr in self.attrs]
        parts = [ensure_str(part) for part in token]
        return ':'.join(parts)

    def _incr_offset_size(self) -> TResumptionToken:
        """Avança o tamanho do deslocamento do offset do token.
        """
        token_map = self._asdict()
        new_offset = self.query_offset() + int(token_map['count'])
        token_map['offset'] = '%s(%s)' % (self.query_from(), new_offset)
        return self.__class__(**token_map)

    def _incr_offset_from(self) -> TResumptionToken:
        """Avança o ano do offset do token, e zera o tamanho do deslocamento.
        """
        token_map = self._asdict()
        new_from = '%s-01-01' % str(int(self.query_from()[:4]) + 1)
        token_map['offset'] = '%s(0)' % new_from
        return self.__class__(**token_map)

    def _has_more_search_space(self) -> bool:
        return self.query_until() < self._upper_limit()

    def next(self, resources: Iterable) -> TResumptionToken:
        """Retorna o próximo resumption token com base no atual e seq de
        ``resources`` resultado da requisição corrente.
        """
        if self._has_more_resources(resources, self.count):
            return self._incr_offset_size()
        elif self._has_more_search_space():
            return self._incr_offset_from()
        else:
            return None

    def _has_more_resources(self, resources: Iterable, batch_size: int) -> bool:
        """Verifica se ``resources`` completa a lista de recursos.

        Se a quantidade de itens em ``resources`` for menor do que ``batch_size``, 
        consideramos se tratar do último conjunto de resultados. Caso a 
        quantidade seja igual, consideramos que existirá o próximo conjunto.
        """
        return len(resources) == int(batch_size)

    def _asdict(self) -> dict:
        """Atua como uma ``namedtuple``, na produção de um dicionário à partir
        de si mesmo.
        """
        return {attr: getattr(self, attr) for attr in self.attrs}

    def __hash__(self):
        return hash((self.__class__, self.encode()))

    def __eq__(self, obj):
        return hash(self) == hash(obj)

    def __repr__(self):
        return '<%s with values %s>' % (self.__class__.__name__, self._asdict())

