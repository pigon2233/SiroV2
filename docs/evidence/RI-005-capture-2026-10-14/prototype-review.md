# RI-005 captured source — independent prototype and design review

2026-10-14（Asia/Taipei）。審查入口為公開 `f3f94c1`：D55是 RI-006唯讀提案，RI-005仍為 D52接口／PARTIAL。此 reviewer只讀production，僅按root要求保存本目錄public own-fixture artifacts。未讀私人DB/chat/key/config/audio/models，未碰live8026、GPU、formal deployment，未改production／tests／launcher／host policy。

## Outcome: identity defect comes before projection

原 `ReleaseManager._digest` 依排序拼接 `relative path bytes + content bytes`，沒有entry framing。兩份相同檔名、不同內容的package能產生完全相同輸入串：

| Package | a | b |
|---|---|---|
| first | ALPHAb | BRAVO |
| second | ALPHA | bBRAVO |

兩者均序列化成 `aALPHAbbBRAVO`。首次直接呼叫當時現有 Core method確認相同digest；保存的 `digest-counterexample.py` 從公開 f3f94c1 Git source擷取同一pure method AST重播，以免root後續修正production影響歷史RED。`digest-counterexample.json`：same filenames=true、different bytes=true、digest equal=true、temporary removed=true。這不是SHA-256 cryptographic collision，是原package encoding非一對一。

分類為已確認 **ORIGINAL_DESIGN_ERROR／BAD_INTERFACE／REQUIRED_FIX HIGH**，root承接 **FIX-020**。完整HMAC manifest若只綁這個ambiguous digest，不能證明精確檔案bytes；memfd/seals只凍結所捕捉的內容，不會修好上游approval identity。因此本輪應先做最小版本化unambiguous digest與complete signing format correction，明確拒舊v1／None進execution，不auto-resign、不靜默重解釋舊signature；歷史v1讀取／serialization保留。具體D56契約與production修復由root負責，本prototype不宣稱該修復完成。

## Actual kernel checks

`kernel-probe.py` 只使用公開 `/usr`與自有temporary fixture；三份合成source/resource與假的dependency/site-hook陷阱，不import真SIRO／provider，不使用實際venv、私人資源或真signing key。Linux bubblewrap0.11.1、system CPython3.14；實際kernel操作，pipe握手控制修改時機。

最後保存的 `kernel-result.json` 有三個joined children，temporary root已移除：

- captured source、晚import與resource保持；host同UID修改原檔及新增module都不影響child所見，完整tree被遮住；package write實際拒絕EROFS。
- 每個memfd使用ALLOW_SEALING／CLOEXEC，加入WRITE／GROW／SHRINK／SEAL；實際write、truncate、writable mmap被拒。parent在child ready後關閉自己的snapshot FDs，晚import／resource仍讀得到kernel內的copy。
- 合成cwd、可寫data、prepared asset與明列dependency保持。`-I -S -B`／手動dependency path避免假的.pth／sitecustomize執行，child沒有key env或故意設inheritable的無關key pipe FD。
- **main-PID TERM graceful=FALSE**：TERM bwrap monitor得到exit-15、沒有child cleanup marker。**owned actual-child TERM graceful=TRUE**：對可信tracked COMMAND PID送TERM，handler／marker完成、exit0、stderr空、child gone。

這些是tiny projection和lifecycle反例，沒有執行完整signed Gateway／schema／readiness／manual approval／maintenance handoff。九項projection checks PASS不等於產品profile或launcher acceptance；monitor TERM反例保留，不改成成功。

## Official interfaces and minimum boundary

官方v0.11.1 `SETUP_MAKE_RO_BIND_FILE` 建新tmpfile、讀來源FD到EOF、關來源FD、把新inode唯讀bind至目標、unlink backing pathname。它是copy而非原inodealias；`--ro-bind-fd`不同。FD讀取不rewind，必須在交付前回到offset0，每個operation用自己的FD。[bubblewrap implementation](https://github.com/containers/bubblewrap/blob/v0.11.1/bubblewrap.c)、[copy_file_data](https://github.com/containers/bubblewrap/blob/v0.11.1/utils.c)、[option contract](https://github.com/containers/bubblewrap/blob/v0.11.1/bwrap.xml)。

有界全tree capture應驗同一份bytes的新unambiguous signed identity，再seal，不能先驗mutablepathname後另copy。每個FD須核對seals、rewind、partial-error cleanup；Bwrap setup消耗來源FD，parent保有自己的duplicate至可靠spawn完成。Popen只pass明列FD、close_fds=True；不能假定COMMAND會自動丟掉所有不相關inheritable FD。[Linux memfd/seals](https://man7.org/linux/man-pages/man2/memfd_create.2.html)、[Python descriptor inheritance](https://docs.python.org/3.14/library/os.html#inheritance-of-file-descriptors)、[Popen pass_fds](https://docs.python.org/3.14/library/subprocess.html#subprocess.Popen)。

完整selected tree須在private namespace重建：只覆蓋既有檔案仍會暴露晚新增module。readonly bind原host tree、chmod或普通temp copy不保證同UID無法改其bytes。

`--bind / /`之後以host-controlled selected path作destination仍有alias門檻；mount會解析destination symlink，不能把先前parent canonical check当成後來mount的authority。固定 `/siro-release`且namespace-private parents比較可靠；runtime `VerifiedRelease.directory`可映射這個唯一readonly root，其version／digest／schema保持同一verifiedcapture。[destination resolution](https://github.com/containers/bubblewrap/blob/v0.11.1/bind-mount.c)。這個固定root與parentrace尚未做kernel驗收，不假稱已PASS。

若先bind整個host根，對不存在的 `/siro-release` mkdir仍落在host根、一般UID可能拒絕；先造private child再bind根也不是保持該child mount的保證。可用private namespace root＋同名trusted host top-level mounts保留絕對data paths。不要把host全移到 `/host`再用symlink鏡射，否則Path.resolve可能把D50 canonical DB key改成 `/host/...`而分裂協調namespace。精確host-root/device／NoNewPrivileges相容性需另有契約與實測，不列已驗全部host權限。

`-I -B`仍執行site initialization／.pth；若要求無hostSIRO preimport，應採trusted `-I -S -B` bootstrap，明列已鎖定的dependency paths並檢查SIRO完整package只從readonlyroot載入。假dependency成功不證明所有現有SDK都相容；mutablevenv／interpreter／OSlibs仍需明確trusted前提，或另一個依賴identity切片。此projection是approved source integrity，不是任意untrusted code隔離。

## Lifecycle is a separate required caller integration

Bwrap最初PID是external monitor，沒有TERM forwarding。`--as-pid-1`只省namespace內第二次reaper fork，不省外部monitor；搭`--unshare-pid`也不能保持現有stop semantics。`--die-with-parent`是SIGKILL保底，不是graceful drain。[v0.11.1 main/monitor](https://github.com/containers/bubblewrap/blob/v0.11.1/bubblewrap.c)、[PDEATHSIG](https://man7.org/linux/man-pages/man2/PR_SET_PDEATHSIG.2const.html)。

後續caller若採Popen，應只在既有launcher composition保有ownedchild，用bounded --info-fd訊息取得實際COMMAND identity，轉送TERM到該child並等待Gateway drain，再joinmonitor；不要先killpg／monitor。需要證明deadline、early spawn/identity-channel失敗、取消／反覆signal、nonzero exit、所有FD與child收尾，未知結果不retry。不是新增daemon／registry／updater／owner。此review與prototype未實作這個caller；D50 CLOEXEC、first-adoption old/unmanagedwriter、maintenance handoff gates保持。

## Reproduction and limits

```bash
python3 docs/evidence/RI-005-capture-2026-10-14/kernel-probe.py > docs/evidence/RI-005-capture-2026-10-14/kernel-result.json
python3 docs/evidence/RI-005-capture-2026-10-14/digest-counterexample.py > docs/evidence/RI-005-capture-2026-10-14/digest-counterexample.json
.venv/bin/ruff format --check docs/evidence/RI-005-capture-2026-10-14/kernel-probe.py docs/evidence/RI-005-capture-2026-10-14/digest-counterexample.py
.venv/bin/ruff check docs/evidence/RI-005-capture-2026-10-14/kernel-probe.py docs/evidence/RI-005-capture-2026-10-14/digest-counterexample.py
```

最後兩scripts真rerun EXIT0；format/lint PASS。首次artifact static check有3項evidence style failure，僅修這兩份evidence script後rerun，沒有production變更或驗收門檻下降。

Rollback只移除此reviewer五份artifact，不回退data／source。所有未知writer、sameUID process注入／mutabledependencies、完整host能力、其他OS、powerloss、formal deployment與existing FIX002/005/006產品門檻未驗；不因原prototype方案能工作而硬加抽象或宣稱RI005完成。
