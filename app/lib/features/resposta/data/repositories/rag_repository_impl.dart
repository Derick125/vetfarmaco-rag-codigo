import 'dart:async';
import 'dart:convert';

import 'package:app/core/error/failures.dart';
import 'package:app/core/network/dio_failure_mapper.dart';
import 'package:app/core/network/sse_parser.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/consulta/domain/corpo_consulta.dart';
import 'package:app/features/resposta/data/datasources/rag_remote_source.dart';
import 'package:app/features/resposta/domain/evento_resposta.dart';
import 'package:app/features/resposta/domain/repositories/rag_repository.dart';
import 'package:dio/dio.dart';
import 'package:fpdart/fpdart.dart';
import 'package:injectable/injectable.dart';

/// Converte uma [MensagemSse] no evento do domínio.
///
/// Lança [FormatException] se o evento for desconhecido ou a carga estiver
/// fora do contrato (`docs/RAG_SPEC.md` §7.1).
EventoResposta eventoDeMensagem(MensagemSse m) {
  try {
    final j = jsonDecode(m.dados) as Map<String, dynamic>;
    switch (m.evento) {
      case 'recuperacao':
        return EventoRecuperacao(
          chunks: j['chunks'] as int,
          ms: (j['ms'] as num).toDouble(),
          thinkingLevel: j['thinkingLevel'] as String?,
        );
      case 'paragrafo':
        return EventoParagrafo(
          indice: j['indice'] as int,
          texto: j['texto'] as String,
          chunkIds: (j['chunkIds'] as List<dynamic>).cast<String>(),
        );
      case 'citacoes':
        return EventoCitacoes([
          for (final c in j['citacoes'] as List<dynamic>)
            _citacao(c as Map<String, dynamic>),
        ]);
      case 'alerta':
        return EventoAlerta(
          severidade: switch (j['severidade']) {
            'contraindicacao' => SeveridadeAlerta.contraindicacao,
            'cautela' => SeveridadeAlerta.cautela,
            _ => throw const FormatException('severidade'),
          },
          texto: j['texto'] as String,
          chunkIds: (j['chunkIds'] as List<dynamic>).cast<String>(),
        );
      case 'fim':
        return _fim(j);
    }
  } on FormatException {
    rethrow;
  } on Object {
    throw const FormatException('Evento fora do contrato.');
  }
  throw FormatException('Evento desconhecido: ${m.evento}');
}

Citacao _citacao(Map<String, dynamic> c) => Citacao(
  chunkId: c['chunkId'] as String,
  indice: c['indice'] as int,
  trecho: c['trecho'] as String,
  fonte: c['fonte'] as String,
  capitulo: c['capitulo'] as String?,
  pagina: c['pagina'] as int?,
);

EventoFim _fim(Map<String, dynamic> j) {
  final uso = (j['usage'] as Map<String, dynamic>?) ?? const {};
  final t = (j['tempos'] as Map<String, dynamic>?) ?? const {};
  double? ms(String k) => (t[k] as num?)?.toDouble();
  return EventoFim(
    nivelConfianca: switch (j['nivelConfianca']) {
      'alta' => NivelConfianca.alta,
      'media' => NivelConfianca.media,
      'baixa' => NivelConfianca.baixa,
      'sem_evidencia' => NivelConfianca.semEvidencia,
      _ => throw const FormatException('nivelConfianca'),
    },
    modelo: j['modelo'] as String,
    thinkingLevel: j['thinkingLevel'] as String?,
    tempos: TemposServidor(
      primeiroToken: ms('msPrimeiroToken'),
      primeiroParagrafoValidado: ms('msPrimeiroParagrafoValidado'),
      total: ms('msTotal'),
    ),
    inputTokens: uso['inputTokens'] as int?,
    outputTokens: uso['outputTokens'] as int?,
    thoughtTokens: uso['thoughtTokens'] as int?,
    custoUsd: (j['custoUsd'] as num?)?.toDouble(),
  );
}

/// [Failure] para um evento `erro` do servidor.
Failure falhaDeErro(MensagemSse m) {
  String? codigo;
  var mensagem = 'O servidor não conseguiu concluir a consulta.';
  try {
    final j = jsonDecode(m.dados) as Map<String, dynamic>;
    codigo = j['codigo'] as String?;
    mensagem = (j['mensagem'] as String?) ?? mensagem;
  } on Object {
    // Carga ilegível: mantém a mensagem genérica.
  }
  return switch (codigo) {
    'citacao_fantasma' || 'inconsistencia_validador' => const FalhaCitacao(
      'A resposta foi descartada: uma citação não pôde ser verificada.',
    ),
    'resposta_invalida' => FalhaContrato(mensagem),
    _ => FalhaServidor(mensagem),
  };
}

/// Implementação de [RagRepository] sobre [RagRemoteSource].
@LazySingleton(as: RagRepository)
class RagRepositoryImpl implements RagRepository {
  /// Cria o repositório.
  const new(this._fonte, this._configuracao);

  final RagRemoteSource _fonte;
  final ConfiguracaoRepository _configuracao;

  @override
  Stream<Either<Failure, EventoResposta>> consultar(
    CorpoConsulta corpo,
  ) async* {
    final endereco = (await _configuracao.enderecoBackend())?.replaceAll(
      RegExp(r'/+$'),
      '',
    );
    if (endereco == null) {
      yield const Left(
        FalhaValidacao('Defina o endereço do back-end em Ajustes.'),
      );
      return;
    }
    try {
      await for (final m in _fonte.consultar(endereco, corpo.paraJson())) {
        if (m.evento == 'erro') {
          yield Left(falhaDeErro(m));
          return;
        }
        final evento = eventoDeMensagem(m);
        yield Right(evento);
        if (evento is EventoFim) return;
      }
      // O stream acabou sem `fim`: resposta incompleta não é sucesso.
      yield const Left(FalhaRede('A conexão foi encerrada antes do fim.'));
    } on DioException catch (e) {
      yield Left(falhaDeDio(e));
    } on FormatException {
      yield const Left(
        FalhaContrato('O servidor enviou uma resposta fora do contrato.'),
      );
    }
  }
}
