import 'dart:convert';

import 'package:app/core/config/app_config.dart';
import 'package:app/core/error/failures.dart';
import 'package:app/core/network/dio_failure_mapper.dart';
import 'package:app/features/bootstrap/domain/repositories/configuracao_repository.dart';
import 'package:app/features/consulta/domain/repositories/vocabulario_repository.dart';
import 'package:app/features/consulta/domain/vocabulario.dart';
import 'package:dio/dio.dart';
import 'package:fpdart/fpdart.dart';
import 'package:hive_ce/hive_ce.dart';
import 'package:injectable/injectable.dart';

/// Chave, na caixa de configuração, da cópia local do vocabulário (JSON).
const chaveVocabulario = 'vocabulario';

/// Lê o vocabulário do JSON do `GET /vocabulario`.
///
/// Lança [FormatException] se o JSON estiver fora do contrato.
Vocabulario vocabularioDeJson(Object? json) {
  try {
    final m = json! as Map<String, dynamic>;
    return Vocabulario(
      versao: m['versao'] as String,
      especies: (m['especies'] as List<dynamic>).cast<String>(),
      farmacos: [
        for (final f in m['farmacos'] as List<dynamic>)
          FarmacoVocabulario(
            nome: (f as Map<String, dynamic>)['nome'] as String,
            sinonimos: (f['sinonimos'] as List<dynamic>).cast<String>(),
          ),
      ],
      comorbidades: [
        for (final c in m['comorbidades'] as List<dynamic>)
          ComorbidadeVocabulario(
            chave: (c as Map<String, dynamic>)['chave'] as String,
            rotulo: c['rotulo'] as String,
          ),
      ],
    );
  } on Object {
    throw const FormatException('Vocabulário fora do contrato.');
  }
}

/// Implementação de [VocabularioRepository]: `dio` + cópia em `hive_ce`.
@LazySingleton(as: VocabularioRepository)
class VocabularioRepositoryImpl implements VocabularioRepository {
  /// Cria o repositório.
  const new(this._dio, this._caixa, this._config, this._configuracao);

  final Dio _dio;
  final Box<dynamic> _caixa;
  final AppConfig _config;
  final ConfiguracaoRepository _configuracao;

  @override
  Future<Either<Failure, Vocabulario>> obter() async {
    final endereco = (await _configuracao.enderecoBackend())?.replaceAll(
      RegExp(r'/+$'),
      '',
    );
    if (endereco == null) {
      return _copiaLocal() ??
          const Left(
            FalhaValidacao('Defina o endereço do back-end em Ajustes.'),
          );
    }
    try {
      final r = await _dio.get<dynamic>(
        '$endereco/vocabulario',
        options: Options(headers: {'X-API-Key': _config.clientApiKey}),
      );
      final vocabulario = vocabularioDeJson(r.data);
      await _guardar(r.data);
      return Right(vocabulario);
    } on DioException catch (e) {
      return _copiaLocal() ?? Left(falhaDeDio(e));
    } on FormatException {
      return _copiaLocal() ??
          const Left(FalhaContrato('Vocabulário recebido fora do contrato.'));
    }
  }

  Future<void> _guardar(Object? json) async {
    try {
      await _caixa.put(chaveVocabulario, jsonEncode(json));
    } on Object {
      // A cópia local é conveniência: falhar ao gravá-la não invalida a
      // resposta que acabou de chegar.
    }
  }

  Either<Failure, Vocabulario>? _copiaLocal() {
    final bruto = _caixa.get(chaveVocabulario);
    if (bruto is! String) return null;
    try {
      return Right(vocabularioDeJson(jsonDecode(bruto)));
    } on FormatException {
      return null;
    }
  }
}
