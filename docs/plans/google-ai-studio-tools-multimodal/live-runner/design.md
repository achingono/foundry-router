# Bounded all-model live validation runner

**Planned**,2026-10-06. User supplied Key Vault credential reference, confirmed five separately
keyed free-tier projects/default limits, and selected all supported models. Agreed caps:
20 requests/20000 tokens/project, zero paidspend. Discovery GETs count toward requestcap;
first1/project already used. All five catalogs contain61models,44generateContent. Discovery
lists IDs/methods, not modality/free-tier support. Exact unsupported/unverified statuses retained.

Runner owns isolated in-process ASGI app with memory stores/one worker and no production calls.
Credential fetch uses AzureCLI capture into memory, timeout30s, exactusersecret reference argument;
never prints exception/stdout/stderr/key/callerbody/provideroutput. Environment-sensitive settings
constructed with explicit config and isolated defaults; backend root fixed Google service HTTPS;
no media/schema/tool egress, no upload/countTokens/autotool. Do not write test config containingkeys.
CLI opt-in --execute plus --manifest reviewedfile; dryrun default. Print/save aggregate caseID,
modelID,capability,projectlabel,counts/status/usage only. Key never argument/env/file outsideAzureCLI
reference; credentialheader injected through existingAllowedBackendClient. CLIerror messages generic.

Manifest lists ALL discoveredmodelIDs and methods; eachrow explicit eligible/requestedcapabilities
or reason excluded. Eligibility requires dated official free-tier evidence for exactmodel; no
substring/name inference or discoverymethod aspricing evidence. Underzero cap no paid-onlymodel
calls. Initially text/nonstream+stream/nativeaudio/video/unsignedtool+schema+image/PDF capabilities
whose code gates pass, with explicit profiles/tokenbounds/operatorfacts. Signature-dependent
models remain unavailable for routerlive because startupgateclosed. Generated output/native-only
methods unavailable until respective codegates. Free-tiercatalogdeprecatedmodel stillrecorded.

Coverage matrix: this runner validates the Google **native** surface only
(`v1beta` `generateContent`/`streamGenerateContent`) — native text first, then gated
native media. It carries no embeddings capability and no compatibility-surface dimension:
embeddings and OpenAI-compat-surface text/streaming/history/embeddings validation belong
to the predecessor [Google AI Studio adapter](../../google-ai-studio-adapter/) contract and
[foundry-inference](../../foundry-inference/) real-inference workflows. Native results here
never close compat gates and compat results never close native gates; each surface keeps
its own manifest rows, protocol proofs and enablement decisions.

Free-tier text-first track (2026-10-07 maintainer direction): Google's free tier grants
usage quotas, not a dollar balance, so validation success is quota admission plus correct
429/cooldown behavior on non-metered backends — local dollar estimates are informational
only there, and routing already treats `credit_metered: false` backends as
quota-gated (`NOT_METERED`, no USD admission fields). The full multimodal plan is
explicitly **not** a prerequisite for this track. Order: (1) two or three free-tier
models, text nonstream then streaming, inside recorded caps; (2) unsigned function tools
for coding-agent use, structured output after; (3) image/PDF input only if real workloads
need it. Audio/video input, generated image/audio, and further signed-state performance
work are parked until chosen models and clients require them. Selected 2026-10-07:
`models/gemini-2.5-flash`, `models/gemini-2.5-flash-lite`, `models/gemini-2.5-pro` —
all free-tier documented with `generateContent` support.

First finite runnable subset text nonstream native: exact manifest eligiblemodelIDs and documented
free-tiertext, requestinput literal syntheticshortprompt/max_output_tokens64/thinkingBudget0;
profilethinkingdisabledtrue. Perrequest reserve inputUTF8bound plusoutput64 (metadataoverhead64);
knownusage retained; unknownusage conservativelyconsumestotalreserved. Pooloneproject/backend
percase, nofailover/retry(retry_attempts0 ifconfigpermits,else1withnoautomaticdispatchretry), count
attempts beforedispatch. Allocate eligiblemodels roundrobinacrossprojects withinremaining19each.
Duplicateversions/aliases eachrow included, nevercollapse basedonname. Configpricedzero with
credit_meteredfalse stillTPM, projectquotagroupseparate. Providererrors safe storedHTTPstatus;
noautomatic retries/newattempts. Nativeadapter errors reportunsupported/incompatible, notsuccess.
No enabledfeatureclaim until requestedcasepasseswithvalidpublicoutput/knownusage. Stream gate
separate; modeltext testdoesnotproveaudio/tools/schema. Requestbudget andtokenreservationcaps
strictbeforeeachdispatch, outputtimeout originalabsolute deadline. CPU/memoryrunninglocally
isolated sameboundedapp; noproduction configread/cutover.

Beforelive: independentreviewofmanifest/runner plusmocked tests: all-modelcoverage/exclusions,
request/tokenceilingatomic/projectgroup, known/missingusage/errorconsumption, retrydisabled,
redaction/error, dryrunnoAzure/provider, nosecretretention. Fullquality/Dockerreview beforeexecute.
Addpercapabilitymanifestrows andsyntheticSDKfixtures onlyaftertheircode/localresourcegatespass.
Ifall-modelmatrixrequiresmorethanbudgetretainuntestedrows; do notinferpermissiontoexceedcaps.

## Independent review revisions

Maintain persistent redacted session ledger initialized discoveryrequests1/project, under an
exclusive filelock, atomicreplace/fsync. Commit request+reservedtoken debit BEFORE actual
AllowedBackendClient transportdispatch await; interrupted/rerun/crash does not resetcaps.
Singleprocess sequentialcases; persistent ledger owns cap20/20000. No failed/ambiguous refunds;
knownusage may reduce only documented successful debit. Actual usage above reservation records
budgetoverrun and haltsproject; cannot claim strictactual ceiling ifproviderignoredtokenbound.
Exactmodel thinkingdisable proof required; initialeligibletext subset narrowedafterthinkingdocs.
Actual discovered manifest is preserved at manifest-discovered.json: all61rows/13explicitfree-tiertextpricing rows; protocolpending. The committed manifest.json is a separate synthetic offline fixture.

SubclassSettings.settings_customise_sources returns ONLYinit_settings; _env_file=None; disable
env/dotenv/secrets/CLI sources. BuildnewFastAPI+build_openai_router with newmemorycredit/rate/
health/metrics, dependencyoverride verify_client_auth owningisolatedsettings/caller. No main.app
import/lifespan/globalstoremutation. Backend constructor add optionalownedsettings? Prefer
reviewedfeaturelocal client factory withtemporaryconstructorpatch onlyinstandaloneprocess,
no-global productionserverreuse. OwnedAsyncBaseTransport wraps boundedHTTPtransport andledger
counting atactualsend; onlyconfiguredGoogleorigin/nativeoperation, headerneverlogs. retry_attempts0,
onebackend/case, nofailover, noautomaticretry. Disablelogginghandler/structlogoutput entirely;
onlyexplicitfixedsummarywriter. subprocesscapturedAzureCLI boundedoutput/noexceptiontracebacks.
Dryrun never initializeskeys/client/app nor readsAzure; onlyvalidatesmanifest/ledger summary.

Code-only review cleared dormant runner on2026-10-06. Use AllowedBackendClient optional owned
settings injection; no constructor/global patch. Zero protocol-approved dispatch cases currently.
