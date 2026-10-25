# Git — lệnh hay dùng (vnstocks / dev.atz.vn)

Tóm tắt cho human. Quy tắc chung: **pull trước khi sửa**, commit **nhỏ**, **không** `git push --force` lên `main`/`master`.

## Mỗi phiên / trước khi code

```bash
git status
git pull --ff-only
```

`--ff-only`: chỉ fast-forward; nếu local lệch remote thì pull báo lỗi — xử lý merge/rebase thủ công, không tự force.

## Xem thay đổi

```bash
git status -sb
git diff                    # chưa stage
git diff --staged           # đã stage
git log -10 --oneline
git log main..HEAD --oneline   # commit trên nhánh hiện tại chưa có trên main
```

## Commit (một phần nhỏ xong)

```bash
git add path/to/file
# hoặc stage theo module:
git add backend/ frontend/ tests/

git commit -m "Mô tả ngắn: vì sao, không chỉ liệt kê file."
```

Commit message nên 1–2 câu, tập trung **why**. Không commit `.env`, token, key.

## Đẩy lên remote

```bash
git push
git push -u origin tên-nhánh   # lần đầu push nhánh mới
```

## Nhánh

```bash
git branch                    # nhánh local
git switch -c feature/ten-viec
git switch main
git fetch origin
```

## Merge / đồng bộ với main

```bash
git fetch origin
git switch main
git pull --ff-only
git switch feature/ten-viec
git merge main                # đưa main mới vào nhánh feature
```

Hoặc trên GitHub: merge PR. Local sau khi PR merge:

```bash
git switch main
git pull --ff-only
git branch -d feature/ten-viec   # xóa nhánh local đã merge (tuỳ chọn)
```

## Bus agent (NOW + task packet)

Khi giao/ack task trên `docs/agents/`:

```bash
git pull --ff-only
git add docs/agents/NOW.md docs/agents/tasks/T-xxx.md
git commit -m "agents: giao task T-xxx / cập nhật NOW"
git push
```

Archive packet (sau ack): thêm `docs/agents/archive/tasks/...` vào `git add` tương tự.

## Khi conflict

```bash
git status                    # file conflict
# sửa file, giữ đúng phần cần
git add path/conflicted-file
git commit                    # hoàn tất merge
```

## Tạm cất việc dở (tuỳ chọn)

```bash
git stash push -m "WIP mô tả ngắn"
git stash list
git stash pop
```

## Không dùng (trừ khi có lý do rõ và đồng ý)

```bash
# git push --force
# git push --force-with-lease   # vẫn nguy hiểm trên main
# git reset --hard
```

## Test nhanh trước commit code

```bash
pytest tests/test_<module>.py -q
```

Thay `<module>` đúng packet đang làm.
