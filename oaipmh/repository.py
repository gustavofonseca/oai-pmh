import re
import functools
import operator
import logging
from typing import Iterable
import urllib.parse

from .formatters import oai_dc
from . import (
        serializers,
        datastores,
        sets,
        )
from .entities import (
        RepositoryMeta,
        OAIRequest,
        MetadataFormat,
        ResumptionToken,
        )


LOGGER = logging.getLogger(__name__)


RESUMPTION_TOKEN_PATTERNS = {
        'ListRecords': re.compile(r'^(\w+)?:((\d{4})-(\d{2})-(\d{2}))?:((\d{4})-(\d{2})-(\d{2}))?:\d+:\d+:\w+$'),
        'ListIdentifiers': re.compile(r'^(\w+)?:((\d{4})-(\d{2})-(\d{2}))?:((\d{4})-(\d{2})-(\d{2}))?:\d+:\d+:$'),
        'ListSets': re.compile(r'^:((\d{4})-(\d{2})-(\d{2}))?:((\d{4})-(\d{2})-(\d{2}))?:\d+:\d+:$'),
        }


OAIPMH_LEGAL_ARGS = set(['verb', 'identifier', 'metadataPrefix', 'set',
            'resumptionToken', 'from', 'until'])


def asdict(namedtupl):
    """Produz uma instância de ``dict`` à partir da namedtuple ``namedtupl``.
    Underscores no início ou fim do nome do atributo serão removidos.
    """
    return {k.strip('_'):v for k, v in namedtupl._asdict().items()}


def serialize_identify(repo: RepositoryMeta, oai_request: OAIRequest) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            }

    return serializers.serialize_identify(data)


def serialize_get_record(repo: RepositoryMeta, oai_request: OAIRequest,
        resource: datastores.Resource, *, metadata_formatter) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            'resources': [asdict(resource)],
            }

    return serializers.serialize_get_record(data, metadata_formatter)


def serialize_list_records(repo: RepositoryMeta, oai_request: OAIRequest,
        resources: Iterable[datastores.Resource],
        resumption_token: ResumptionToken, *, metadata_formatter) -> bytes:

    if resumption_token is None:
        encoded_resumption_token = ''
    else:
        encoded_resumption_token = encode_resumption_token(resumption_token)

    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            'resources': (asdict(resource) for resource in resources),
            'resumptionToken': encoded_resumption_token,
            }
    return serializers.serialize_list_records(data, metadata_formatter)


def serialize_list_identifiers(repo: RepositoryMeta, oai_request: OAIRequest,
        resources: Iterable[datastores.Resource],
        resumption_token: ResumptionToken) -> bytes:

    if resumption_token is None:
        encoded_resumption_token = ''
    else:
        encoded_resumption_token = encode_resumption_token(resumption_token)

    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            'resources': (asdict(resource) for resource in resources),
            'resumptionToken': encoded_resumption_token,
            }

    return serializers.serialize_list_identifiers(data)


def serialize_list_metadata_formats(repo: RepositoryMeta, oai_request: OAIRequest,
        formats: Iterable[MetadataFormat]) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            'formats': (asdict(fmt) for fmt in formats),
            }

    return serializers.serialize_list_metadata_formats(data)


def serialize_list_sets(repo: RepositoryMeta, oai_request: OAIRequest,
        sets: Iterable[sets.Set],
        resumption_token: ResumptionToken,) -> bytes:

    if resumption_token is None:
        encoded_resumption_token = ''
    else:
        encoded_resumption_token = encode_resumption_token(resumption_token)

    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            'sets': (asdict(s) for s in sets),
            'resumptionToken': encoded_resumption_token,
            }
    return serializers.serialize_list_sets(data)


def serialize_bad_verb(repo: RepositoryMeta, oai_request: OAIRequest) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            }

    return serializers.serialize_bad_verb(data)


def serialize_bad_argument(repo: RepositoryMeta,
        oai_request: OAIRequest) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            }

    return serializers.serialize_bad_argument(data)


def serialize_id_does_not_exist(repo: RepositoryMeta,
        oai_request: OAIRequest) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            }

    return serializers.serialize_id_does_not_exist(data)


def serialize_cannot_disseminate_format(repo: RepositoryMeta,
        oai_request: OAIRequest) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            }

    return serializers.serialize_cannot_disseminate_format(data)


def serialize_bad_resumption_token(repo: RepositoryMeta,
        oai_request: OAIRequest) -> bytes:
    data = {
            'repository': asdict(repo),
            'request': asdict(oai_request),
            }

    return serializers.serialize_bad_resumption_token(data)


class BadArgumentError(Exception):
    """Lançada quando a requisição contém argumentos inválidos para o verbo
    definido.
    """


class BadResumptionTokenError(Exception):
    """Lançada quando o valor do argumento ``resumptionToken`` é inválido.
    """


class SetNameError(Exception):
    """Lançada quando se tenta obter a view de um set inexistente.
    """


class check_request_args:
    """Valida os argumentos da requisição de acordo com as regras de cada verbo.

    :param checking_func: função que receberá como argumento a sequência de
    nomes dos atributos recebidos na requisição. A função deve retornar um
    valor booleano referente à validade dos atributos.
    """
    def __init__(self, checking_func):
        self.checking_func = checking_func

    def __call__(self, f):
        def wrapper(*args):
            _, oaireq = args
            detected_args = [k for k, v in asdict(oaireq).items() if v]
            if self.checking_func(detected_args):
                return f(*args)
            else:
                raise BadArgumentError()
        return wrapper


def are_equal(expected_args, detected_args):
    return sorted(expected_args) == sorted(detected_args)


def check_listrecords_args(detected_args):
    args = set(detected_args)
    if 'verb' not in args:
        return False

    if 'resumptionToken' in args:
        return not any((operator.contains(args, arg)
                        for arg in ['from', 'until', 'set', 'metadataPrefix']))
    else:
        return 'metadataPrefix' in args


def check_listidentifiers_args(detected_args):
    args = set(detected_args)
    if 'verb' not in args:
        return False

    if 'resumptionToken' in args:
        return not any((operator.contains(args, arg)
                        for arg in ['from', 'until', 'set', 'metadataPrefix']))
    else:
        return 'metadataPrefix' not in args


def check_listsets_args(detected_args):
    args = set(detected_args)
    if 'verb' not in args:
        return False

    if 'resumptionToken' in args:
        return not any((operator.contains(args, arg)
                        for arg in ['from', 'until', 'set']))
    else:
        return 'metadataPrefix' not in args


def get_or_default(mapping, key, default=None):
    """Retorna o valor do índice 0 de ``mapping[key]`` ou ``default``.
    """
    try:
        values = mapping[key]
    except KeyError:
        return default
    return values[0]


def has_illegal_args(parsed_qstr, legal_args=OAIPMH_LEGAL_ARGS):
    for arg in parsed_qstr.keys():
        if arg not in legal_args:
            return True
    return False


def has_repeated_args(parsed_qstr):
    for value in parsed_qstr.values():
        if len(value) > 1:
            return True
    return False


def oairequest_from_querystring(parsed_qstr):
    return OAIRequest(
            verb=get_or_default(parsed_qstr, 'verb'),
            identifier=get_or_default(parsed_qstr, 'identifier'),
            metadataPrefix=get_or_default(parsed_qstr, 'metadataPrefix'),
            set=get_or_default(parsed_qstr, 'set'),
            resumptionToken=get_or_default(parsed_qstr, 'resumptionToken'),
            from_=get_or_default(parsed_qstr, 'from'),
            until=get_or_default(parsed_qstr, 'until'),
            )


class Repository:
    def __init__(self, metadata: RepositoryMeta, ds: datastores.DataStore,
            setsreg: sets.SetsRegistry, listslen: int):
        self.metadata = metadata
        self.ds = ds
        self.setsreg = setsreg
        self.listslen = listslen
        self.formats = {}
        self.verbs = {
                'Identify': self.identify,
                'GetRecord': self.get_record,
                'ListRecords': self.list_records,
                'ListIdentifiers': self.list_identifiers,
                'ListMetadataFormats': self.list_metadata_formats,
                'ListSets': self.list_sets,
                }

    def add_metadataformat(self, metadata: MetadataFormat, formatter, augmenter):
        """Registra formatos de metadados suportados pelo repositório.

        :param metadata: descreve o formato.
        :param formatter: função que dado um dicionário, produz uma árvore de 
        elementos XML (etree.Element).
        :param augmenter: função que dado um dicionário, produz outro dicionário.
        Este último será o argumento para a função ``formatter``.
        """
        self.formats[metadata.metadataPrefix] = {
                'metadata': metadata,
                'formatter': formatter,
                'augmenter': augmenter,
                }

    def handle_request(self, qstr: str):
        """Trata a requisição ``qstr`` codificada como querystring.
        """
        parsed_qstr = urllib.parse.parse_qs(qstr)
        oairequest = oairequest_from_querystring(parsed_qstr)

        LOGGER.info('handling OAI request: %s', repr(oairequest))

        if has_illegal_args(parsed_qstr) or has_repeated_args(parsed_qstr):
            return serialize_bad_argument(self.metadata, oairequest)

        try:
            verb = self.verbs[oairequest.verb]
        except KeyError:
            return serialize_bad_verb(self.metadata, oairequest)

        try:
            return verb(oairequest)
        except (BadArgumentError, SetNameError):
            return serialize_bad_argument(self.metadata, oairequest)
        except datastores.DoesNotExistError:
            return serialize_id_does_not_exist(self.metadata, oairequest)
        except BadResumptionTokenError:
            return serialize_bad_resumption_token(self.metadata, oairequest)

    @check_request_args(functools.partial(are_equal, ['verb']))
    def identify(self, oairequest: OAIRequest) -> bytes:
        return serialize_identify(self.metadata, oairequest)

    @check_request_args(functools.partial(are_equal, 
        ['verb', 'metadataPrefix', 'identifier']))
    def get_record(self, oairequest: OAIRequest) -> bytes:
        if oairequest.metadataPrefix not in self.formats:
            return serialize_cannot_disseminate_format(self.metadata, oairequest)

        fmt = self.formats[oairequest.metadataPrefix]
        resource = fmt['augmenter'](self.ds.get(oairequest.identifier))
        return serialize_get_record(self.metadata, oairequest, resource,
                metadata_formatter=fmt['formatter'])

    def _filter_records(self, token: ResumptionToken):
        view = self.setsreg.get_view(token.set)
        if view is None:
            raise SetNameError('Cannot find a view for set "%s"', token.set)

        resources = self.ds.list(int(token.offset), int(token.count),
                view=view, _from=token.from_, until=token.until)
        return resources

    @check_request_args(check_listrecords_args)
    def list_records(self, oairequest: OAIRequest) -> bytes:
        if not oairequest.resumptionToken:
            if oairequest.metadataPrefix not in self.formats:
                return serialize_cannot_disseminate_format(self.metadata, oairequest)

        token = get_resumption_token_from_request(oairequest, self.listslen)
        fmt = self.formats[token.metadataPrefix]
        resources = list((fmt['augmenter'](r)
                          for r in self._filter_records(token)))
        next_token = next_resumption_token(token, resources)
        return serialize_list_records(self.metadata, oairequest, resources,
                next_token, metadata_formatter=fmt['formatter'])

    @check_request_args(check_listidentifiers_args)
    def list_identifiers(self, oairequest: OAIRequest) -> bytes:
        token = get_resumption_token_from_request(oairequest, self.listslen)
        resources = list(self._filter_records(token))
        next_token = next_resumption_token(token, resources)
        return serialize_list_identifiers(self.metadata, oairequest, resources,
                next_token)

    @check_request_args(functools.partial(are_equal, ['verb']))
    def list_metadata_formats(self, oairequest: OAIRequest) -> bytes:
        fmts = [fmt['metadata'] for fmt in self.formats.values()]
        return serialize_list_metadata_formats(self.metadata, oairequest, fmts)

    @check_request_args(check_listsets_args)
    def list_sets(self, oairequest: OAIRequest) -> bytes:
        token = get_resumption_token_from_request(oairequest, self.listslen)
        sets_list = list(self.setsreg.list(int(token.offset), int(token.count)))
        next_token = next_resumption_token(token, sets_list)
        return serialize_list_sets(self.metadata, oairequest, sets_list,
                next_token)


def get_resumption_token_from_request(oairequest: OAIRequest,
        default_count: int) -> ResumptionToken:
    """Obtém um ``ResumptionToken`` à partir do ``oairequest``.

    Caso o token não seja válido sintaticamente ou o valor do atributo ``count``
    seja diferente de ``default_count``, levanta a exceção ``BadResumptionToken``;
    Retorna um novo ``ResumptionToken`` caso não haja um codificado no
    ``oairequest``.
    """
    if oairequest.resumptionToken:
        pattern = RESUMPTION_TOKEN_PATTERNS[oairequest.verb]
        if not is_valid_resumption_token(oairequest.resumptionToken, pattern):
            raise BadResumptionTokenError()

        token = decode_resumption_token(oairequest.resumptionToken)
        if int(token.count) != default_count:
            raise BadResumptionTokenError('token count is different than ``oaipmh.listslen``')
    else:
        token = ResumptionToken(set=oairequest.set, from_=oairequest.from_,
                until=oairequest.until, offset='0', count=default_count,
                metadataPrefix=oairequest.metadataPrefix)

    return token


def encode_resumption_token(token: ResumptionToken) -> str:
    """Codifica o ``token`` em string delimitada por ``:``.

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

    parts = [ensure_str(part) for part in token]
    return ':'.join(parts)


def decode_resumption_token(token: str) -> ResumptionToken:
    keys = ResumptionToken._fields
    values = token.split(':')
    kwargs = dict(zip(keys, values))
    return ResumptionToken(**kwargs)


def inc_resumption_token(token: ResumptionToken) -> ResumptionToken:
    """Avança o offset do token.
    """
    token_map = token._asdict()
    new_offset = 1 + int(token_map['offset']) + int(token_map['count'])
    token_map['offset'] = str(new_offset)
    return ResumptionToken(**token_map)


def has_more_resources(resources: Iterable, batch_size: int) -> bool:
    """Verifica se ``resources`` completa a lista de recursos.

    Se a quantidade de itens em ``resources`` for menor do que ``batch_size``, 
    consideramos se tratar do último conjunto de resultados. Caso a 
    quantidade seja igual, consideramos que existirá o próximo conjunto.
    """
    return len(resources) == int(batch_size)


def next_resumption_token(token: ResumptionToken, resources: Iterable) -> ResumptionToken:
    """Retorna o próximo resumption token com base no atual e seq de
    ``resources`` resultado da requisição corrente.
    """
    if has_more_resources(resources, token.count):
        return inc_resumption_token(token)
    else:
        return None


def is_valid_resumption_token(token: str, pattern: str) -> bool:
    """Se o valor de ``token`` é válido sintaticamente.
    """
    return bool(pattern.fullmatch(token))

