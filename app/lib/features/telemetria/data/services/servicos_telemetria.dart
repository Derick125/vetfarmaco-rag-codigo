import 'dart:convert';
import 'dart:typed_data';

import 'package:app/core/error/failures.dart';
import 'package:app/features/telemetria/domain/repositories/telemetria_repository.dart';
import 'package:connectivity_plus/connectivity_plus.dart';
import 'package:fpdart/fpdart.dart';
import 'package:injectable/injectable.dart';
import 'package:share_plus/share_plus.dart';

/// [CondicaoRede] sobre `connectivity_plus`.
///
/// O pacote distingue Wi-Fi de rede móvel, mas não 4G de 5G: a condição da
/// campanha (4G/5G) é anotada à parte na análise do CSV.
@LazySingleton(as: CondicaoRede)
class CondicaoRedeConnectivity implements CondicaoRede {
  /// Cria o serviço.
  const new();

  @override
  Future<String> atual() async {
    try {
      final r = await Connectivity().checkConnectivity();
      return r.isEmpty
          ? 'desconhecida'
          : (r.map((e) => e.name).toList()..sort()).join('+');
    } on Object {
      return 'desconhecida';
    }
  }
}

/// [CompartilhadorCsv] sobre `share_plus`.
@LazySingleton(as: CompartilhadorCsv)
class CompartilhadorSharePlus implements CompartilhadorCsv {
  /// Cria o serviço.
  const new();

  @override
  Future<Either<Failure, Unit>> compartilhar(
    String nome,
    String conteudo,
  ) async {
    try {
      // BOM para o Excel reconhecer UTF-8 (acentos).
      final bytes = Uint8List.fromList([
        0xEF,
        0xBB,
        0xBF,
        ...utf8.encode(conteudo),
      ]);
      await SharePlus.instance.share(
        ShareParams(
          files: [XFile.fromData(bytes, mimeType: 'text/csv')],
          fileNameOverrides: [nome],
          subject: nome,
        ),
      );
      return const Right(unit);
    } on Object {
      return const Left(
        FalhaCache('Não foi possível abrir o compartilhamento.'),
      );
    }
  }
}
