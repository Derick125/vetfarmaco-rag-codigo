import 'dart:convert';

import 'package:app/core/error/failures.dart';
import 'package:app/core/network/sse_parser.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/historico/domain/repositories/resposta_cache_repository.dart';
import 'package:app/features/historico/domain/resposta_salva.dart';
import 'package:app/features/resposta/data/repositories/rag_repository_impl.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:injectable/injectable.dart';

/// Nome da caixa `hive_ce` das respostas guardadas.
const nomeCaixaRespostas = 'respostas';

/// Serializa [r] com os mesmos formatos do stream SSE (`RAG_SPEC.md` §7.1):
/// ler de volta passa pelo mesmo parser que valida o que vem do servidor.
String respostaParaJson(RespostaSalva r) => jsonEncode({
  'corpo': r.corpo.paraJson(),
  'geradaEm': r.geradaEm.toUtc().toIso8601String(),
  'paragrafos': [
    for (final p in r.paragrafos)
      {'indice': p.indice, 'texto': p.texto, 'chunkIds': p.chunkIds},
  ],
  'citacoes': {
    'citacoes': [
      for (final c in r.citacoes)
        {
          'chunkId': c.chunkId,
          'indice': c.indice,
          'trecho': c.trecho,
          'fonte': c.fonte,
          'capitulo': c.capitulo,
          'pagina': c.pagina,
        },
    ],
  },
  'alerta': r.alerta == null
      ? null
      : {
          'severidade': r.alerta!.severidade.name,
          'texto': r.alerta!.texto,
          'chunkIds': r.alerta!.chunkIds,
        },
  'fim': {
    'nivelConfianca': r.fim.nivelConfianca == NivelConfianca.semEvidencia
        ? 'sem_evidencia'
        : r.fim.nivelConfianca.name,
    'modelo': r.fim.modelo,
    'thinkingLevel': r.fim.thinkingLevel,
    'usage': {
      'inputTokens': r.fim.inputTokens,
      'outputTokens': r.fim.outputTokens,
      'thoughtTokens': r.fim.thoughtTokens,
    },
    'custoUsd': r.fim.custoUsd,
    'tempos': {
      'msPrimeiroToken': r.fim.tempos.primeiroToken,
      'msPrimeiroParagrafoValidado': r.fim.tempos.primeiroParagrafoValidado,
      'msTotal': r.fim.tempos.total,
    },
  },
});

/// Lê o JSON gravado por [respostaParaJson]; lança [FormatException] se
/// estiver corrompido.
RespostaSalva respostaDeJson(String bruto) {
  try {
    final j = jsonDecode(bruto) as Map<String, dynamic>;
    T evento<T extends EventoResposta>(String nome, Object? dados) =>
        eventoDeMensagem(MensagemSse(evento: nome, dados: jsonEncode(dados)))
            as T;
    final alerta = j['alerta'];
    return RespostaSalva(
      corpo: CorpoConsulta.deJson(j['corpo'] as Map<String, dynamic>),
      geradaEm: DateTime.parse(j['geradaEm'] as String),
      paragrafos: [
        for (final p in j['paragrafos'] as List<dynamic>)
          evento<EventoParagrafo>('paragrafo', p),
      ],
      citacoes: evento<EventoCitacoes>('citacoes', j['citacoes']).citacoes,
      alerta: alerta == null ? null : evento<EventoAlerta>('alerta', alerta),
      fim: evento<EventoFim>('fim', j['fim']),
    );
  } on FormatException {
    rethrow;
  } on Object {
    throw const FormatException('Resposta salva corrompida.');
  }
}

/// [RespostaCacheRepository] sobre uma caixa `hive_ce`.
@LazySingleton(as: RespostaCacheRepository)
class RespostaCacheRepositoryImpl implements RespostaCacheRepository {
  /// Cria o repositório.
  const new(@Named('respostas') this._caixa);

  final Box<dynamic> _caixa;

  @override
  Future<Either<Failure, Unit>> salvar(RespostaSalva resposta) async {
    try {
      await _caixa.put(resposta.chave, respostaParaJson(resposta));
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível salvar a resposta.'));
    }
  }

  @override
  Future<Either<Failure, RespostaSalva?>> buscar(String chave) async {
    try {
      final bruto = _caixa.get(chave);
      if (bruto is! String) return const Right(null);
      final r = respostaDeJson(bruto);
      // Guarda contra colisão do hash: só serve se for a mesma consulta.
      return Right(r.chave == chave ? r : null);
    } on Object {
      return const Left(FalhaCache('Não foi possível ler a resposta salva.'));
    }
  }

  @override
  Future<Either<Failure, List<RespostaSalva>>> historico() async {
    try {
      final lista = [
        for (final bruto in _caixa.values) respostaDeJson(bruto as String),
      ]..sort((a, b) => b.geradaEm.compareTo(a.geradaEm));
      return Right(lista);
    } on Object {
      return const Left(FalhaCache('Não foi possível ler o histórico.'));
    }
  }

  @override
  Future<Either<Failure, Unit>> remover(String chave) async {
    try {
      await _caixa.delete(chave);
      return const Right(unit);
    } on Object {
      return const Left(FalhaCache('Não foi possível remover a resposta.'));
    }
  }
}
