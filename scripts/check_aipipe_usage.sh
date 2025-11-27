AIPIPE_TOKEN=
curl -s https://aipipe.org/usage -H "Authorization: Bearer $AIPIPE_TOKEN" | jq -r '"\(.email) used \(.cost * 1000000 | round/10000) cents out of \(.limit * 100) cents limit."'
