import 'package:app/core/error/failures.dart';
import 'package:app/features/telemetria/domain/registro_telemetria.dart';
import 'package:fpdart/fpdart.dart';

/// Armazenamento local das medições (`hive_ce`).
abstract interface class TelemetriaRepository {
  /// Grava [registro].
  Future<Either<Failure, Unit>> gravar(RegistroTelemetria registro);

  /// Todos os registros, do mais antigo ao mais novo.
  Future<Either<Failure, List<RegistroTelemetria>>> listar();
}

/// Condição de rede do aparelho no momento do envio.
abstract interface class CondicaoRede {
  /// Rótulo da conexão (`wifi`, `mobile`, `none`…); nunca lança.
  Future<String> atual();
}

/// Entrega um arquivo CSV ao usuário (folha de compartilhamento).
abstract interface class CompartilhadorCsv {
  /// Compartilha [conteudo] como arquivo [nome].
  Future<Either<Failure, Unit>> compartilhar(String nome, String conteudo);
}
