import 'package:app/core/error/failures.dart';
import 'package:equatable/equatable.dart';

/// Estados do termo de uso (`docs/FRONTEND_SPEC.md` §8).
sealed class TermoState extends Equatable {
  const new();

  @override
  List<Object?> get props => [];
}

/// Termo ainda não aceito; [falha] é preenchida se a gravação falhou.
class NaoAceito extends TermoState {
  /// Cria o estado.
  const new({this.falha});

  /// Falha da última tentativa de aceitar, se houve.
  final Failure? falha;

  @override
  List<Object?> get props => [falha];
}

/// Termo aceito em [quando].
class Aceito extends TermoState {
  /// Cria o estado.
  const new(this.quando);

  /// Data/hora do aceite.
  final DateTime quando;

  @override
  List<Object?> get props => [quando];
}
