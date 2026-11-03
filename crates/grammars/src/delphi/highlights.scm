; Adapted from Isopod/tree-sitter-pascal, MIT; see LICENSE.tree-sitter-pascal.
; -- Keywords
[
	(kProgram)
	(kPackage)
	(kRequires)
	(kContains)
	(kLibrary)
	(kUnit)
	(kUses)

	(kBegin)
	(kEnd)
	(kAsm)

	(kVar)
	(kThreadvar)
	(kConst)
	(kResourcestring)
	(kConstref)
	(kOut)
	(kType)
	(kLabel)
	(kExports)

	(kAbsolute)

	(kProperty)
	(kRead)
	(kWrite)
	(kImplements)
	(kDefault)
	(kNodefault)
	(kStored)
	(kIndex)
	(kDispId)

	(kClass)
	(kInterface)
	(kDispInterface)
	(kObject)
	(kRecord)
	(kObjcclass)
	(kObjccategory)
	(kObjcprotocol)
	(kArray)
	(kFile)
	(kString)
	(kSet)
	(kOf)
	(kHelper)
	(kPacked)

	(kGeneric)
	(kSpecialize)

	(kFunction)
	(kProcedure)
	(kConstructor)
	(kDestructor)
	(kOperator)
	(kReference)

	(kInterface)
	(kImplementation)
	(kInitialization)
	(kFinalization)

	(kPublished)
	(kPublic)
	(kProtected)
	(kPrivate)
	(kStrict)
	(kRequired)
	(kOptional)

	(kForward)

	(kStatic)
	(kVirtual)
	(kAbstract)
	(kSealed)
	(kDynamic)
	(kOverride)
	(kOverload)
	(kReintroduce)
	(kInherited)
	(kInline)

	(kStdcall)
	(kCdecl)
	(kCppdecl)
	(kPascal)
	(kRegister)
	(kMwpascal)
	(kExternal)
	(kName)
	(kMessage)
	(kDeprecated)
	(kExperimental)
	(kPlatform)
	(kUnimplemented)
	(kCvar)
	(kExport)
	(kFar)
	(kNear)
	(kSafecall)
	(kAssembler)
	(kNostackframe)
	(kInterrupt)
	(kNoreturn)
	(kIocheck)
	(kLocal)
	(kHardfloat)
	(kSoftfloat)
	(kMs_abi_default)
	(kMs_abi_cdecl)
	(kSaveregisters)
	(kSysv_abi_default)
	(kSysv_abi_cdecl)
	(kVectorcall)
	(kVarargs)
	(kWinapi)
	(kAlias)
	(kDelayed)

	(kFor)
	(kTo)
	(kDownto)
	(kIf)
	(kThen)
	(kElse)
	(kDo)
	(kWhile)
	(kRepeat)
	(kUntil)
	(kTry)
	(kExcept)
	(kFinally)
	(kRaise)
	(kOn)
	(kCase)
	(kWith)
	(kGoto)
] @keyword

; -- Punctuation & operators

[
	"("
	")"
	"["
	"]"
] @punctuation.bracket

[
	";"
	","
	":"
	".."
	(kEndDot)
] @punctuation.delimiter

[
	(kDot)
	(kAdd)
	(kSub)
	(kMul)
	(kFdiv)
	(kAssign)
	(kAssignAdd)
	(kAssignSub)
	(kAssignMul)
	(kAssignDiv)
	(kEq)
	(kLt)
	(kLte)
	(kGt)
	(kGte)
	(kNeq)
	(kAt)
	(kHat)
] @operator

; technically operators, but better to render as reserved words
[
	(kOr)
	(kXor)
	(kDiv)
	(kMod)
	(kAnd)
	(kShl)
	(kShr)
	(kNot)
	(kIs)
	(kAs)
	(kIn)
] @keyword

; -- Builtin constants

[
	(kTrue)
	(kFalse)
] @constant;

; arguably a constant, but we highlight it as a keyword
[
	(kNil)
] @keyword

; -- Literals

(literalNumber)   @number
(literalString)   @string

; -- Comments
(comment)         @comment
(pp)              @keyword

; -- Type declaration

(declType name: (identifier) @type)
(declType name: (genericTpl entity: (identifier) @type))

; -- Procedure & function declarations

; foobar
(declProc name: (identifier) @function)
; foobar<t>
(declProc name: (genericTpl entity: (identifier) @function))
; foo.bar
(declProc name: (genericDot rhs: (identifier) @function))
; foo.bar<t>
(declProc name: (genericDot rhs: (genericTpl entity: (identifier) @function)))

; Treat property declarations like functions

(declProp name: (identifier) @property)

; -- Function parameters

(declArg name: (identifier) @variable)

; -- Template parameters

(genericArg	name: (identifier) @type)
(genericArg	type: (typeref) @type)

(genericDot (identifier) @type)
(genericDot (genericTpl entity: (identifier) @type))

; -- Exception parameters
(exceptionHandler variable: (identifier) @variable)

; -- Type usage

(typeref) @type

; -- Constant usage

[
	(caseLabel)
	(label)
] @constant;


