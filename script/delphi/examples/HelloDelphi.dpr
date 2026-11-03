program HelloDelphi;

{$APPTYPE CONSOLE}

uses
  SysUtils;

function Add(Left, Right: Integer): Integer;
begin
  Result := Left + Right;
end;

var
  Total: Integer;
begin
  Total := Add(20, 22);
  WriteLn('Delphi result: ', Total);
end.
