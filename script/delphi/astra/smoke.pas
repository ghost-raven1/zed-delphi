program AstraFpcSmoke;

uses
  SysUtils, Classes, Generics.Collections, fpjson;

type
  TAccumulator = class
  private
    FTotal: Integer;
  public
    procedure Add(Value: Integer);
    property Total: Integer read FTotal;
  end;

procedure TAccumulator.Add(Value: Integer);
begin
  FTotal := FTotal + Value;
end;

var
  Values: TList<Integer>;
  Accumulator: TAccumulator;
  Payload: TJSONObject;
  Value: Integer;
begin
  Values := TList<Integer>.Create;
  Accumulator := TAccumulator.Create;
  try
    Values.Add(20);
    Values.Add(22);
    for Value in Values do
      Accumulator.Add(Value);
    Payload := TJSONObject.Create(['answer', Accumulator.Total]);
    try
      if Payload.Get('answer', 0) <> 42 then
        Halt(1);
      WriteLn('ASTRA_FPC_SMOKE_OK:', Payload.Get('answer', 0));
    finally
      Payload.Free;
    end;
  finally
    Accumulator.Free;
    Values.Free;
  end;
end.
