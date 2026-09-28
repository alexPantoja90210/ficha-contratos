# Deploying the sheet on AWS

The sheet runs as a single Lambda function behind a Function URL, with the page on
S3. There is no vector store, no embedding model and no LLM in this stack, because
the sheet does not use one: it is rules plus term retrieval over the Python
standard library, and it answers in milliseconds.

Everything below was measured, not estimated.

| | |
|---|---|
| Deployment package | **34 KB**, 8 modules and 3 data files, no dependencies to vendor |
| Cold import | **28 ms** (module load, fitted model, scope decision) |
| Per request, median contract | **5 ms** |
| Per request, largest contract in CUAD (330 KB) | **100 ms** |
| Peak memory, largest contract | **7.3 MB** of Python heap, 25 MB RSS |
| Largest contract as a JSON request body | 334 KB, against Lambda's 6 MB limit — **18x of headroom** |

Because the package has no third-party code, there is no layer, no container image
and no `pip install` step. That is a property of the design, and it is the reason
this deploys in four commands.

## Before you start

- The AWS CLI, signed in: `aws sts get-caller-identity` should print your account.
- Python 3 to build the package. Verified identical on 3.10, 3.12 and 3.13.
- The commands below are written for **PowerShell on Windows**. Every JSON argument
  is read from a file in `aws/` rather than typed inline, which sidesteps
  PowerShell's quoting rules entirely.

Set these once per session:

```powershell
$REGION = "us-east-1"
$FN     = "contract-clause-sheet"
$ACCT   = (aws sts get-caller-identity --query Account --output text)
```

## 1. Build the package

```powershell
python build_lambda.py
```

Writes `sheet-lambda.zip`. Rerun it after any change to the code or the fitted
model; it is the only build step.

## Creating it in the console instead

Steps 2 to 4 below are the CLI path. The same three things can be made in the
console, which creates the execution role for you and writes the Function URL
permission policy automatically:

1. **Lambda → Create function → Author from scratch.** Name it, choose runtime
   **Python 3.13**, architecture x86_64. Under *Change default execution role*,
   leave **Create a new role with basic Lambda permissions** — that is the same
   least-privilege role step 2 builds by hand.
2. **Configuration → General configuration → Edit:** memory **512 MB**,
   timeout **10 sec**.
3. **Code → Upload from → .zip file**, and pick `sheet-lambda.zip`. Then
   **Runtime settings → Edit** and set the handler to
   `lambda_function.handler` — the console defaults to `lambda_function.lambda_handler`,
   which does not exist here and fails at the first invocation.
4. **Configuration → Function URL → Create function URL:** auth type **NONE**,
   tick **Configure cross-origin resource sharing (CORS)**, and set
   *Allow origin* to `*`, *Allow headers* to `content-type`, *Allow methods* to
   `GET` and `POST`.

After that, `aws lambda update-function-code` (see *Updating*) is the fastest way
to push later changes without clicking through the console again.

## 2. The execution role

Least privilege: the function writes its own logs and does nothing else. It reads
no S3 bucket, calls no other service, and needs no inline policy.

```powershell
aws iam create-role --role-name "$FN-role" --assume-role-policy-document file://aws/trust-policy.json
aws iam attach-role-policy --role-name "$FN-role" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
```

Wait about ten seconds before the next step: a brand-new role is not immediately
visible to Lambda, and creating the function too quickly fails with
`The role defined for the function cannot be assumed by Lambda`.

## 3. The function

```powershell
aws lambda create-function `
  --function-name $FN `
  --runtime python3.13 `
  --handler lambda_function.handler `
  --role "arn:aws:iam::${ACCT}:role/$FN-role" `
  --zip-file fileb://sheet-lambda.zip `
  --timeout 10 `
  --memory-size 512 `
  --region $REGION
```

**On 512 MB:** the function peaks at 25 MB, so memory is not the constraint —
Lambda scales CPU with the memory setting, and 512 MB is where the 330 KB worst
case stays around 100 ms. At 128 MB it still runs, just slower. The cost
difference is discussed at the end and it is not the deciding factor.

**On a 10-second timeout:** the worst measured case is 100 ms. Ten seconds is a
hundredfold margin that exists to turn a hang into a clean error rather than a
long bill.

## 4. The Function URL

```powershell
aws lambda create-function-url-config --function-name $FN --auth-type NONE --cors file://aws/cors.json --region $REGION

aws lambda add-permission `
  --function-name $FN `
  --statement-id FunctionURLAllowPublicAccess `
  --action lambda:InvokeFunctionUrl `
  --principal "*" `
  --function-url-auth-type NONE `
  --region $REGION

aws lambda add-permission `
  --function-name $FN `
  --statement-id FunctionURLAllowInvoke `
  --action lambda:InvokeFunction `
  --principal "*" `
  --invoked-via-function-url `
  --region $REGION
```

**Those permission commands are not optional on this path.** A Function URL with
`--auth-type NONE` still returns `403 Forbidden` until the resource policy exists,
and it is the most common reason a fresh Function URL appears broken.

**Creating the URL in the console instead? Skip them.** When the URL is created
with auth type NONE through the console or AWS SAM, Lambda writes the resource
policy for you. Only the CLI, the API and CloudFormation leave it to you. Note
that deleting the URL does not remove the policy either way — the teardown
section handles that.

Get the URL:

```powershell
$URL = (aws lambda get-function-url-config --function-name $FN --region $REGION --query FunctionUrl --output text)
$URL
```

`--auth-type NONE` means anyone with the URL can call it. That is the intent for a
public demo. It is also why the handler caps the request at 1,000,000 characters
and never writes contract text to the log.

## 5. Check it

```powershell
# what the sheet covers, and the criterion behind it
curl.exe $URL

# a contract in, the sheet out
'{"text":"THIS AGREEMENT is entered into as of March 14, 2018 and shall be governed by the laws of the State of New York."}' | Out-File -Encoding utf8 body.json
curl.exe -X POST $URL -H "content-type: application/json" --data-binary "@body.json"
```

Use `curl.exe`, not `curl`: in PowerShell, `curl` is an alias for
`Invoke-WebRequest`, which takes different arguments and will confuse the error.

## 6. The page

```powershell
$BUCKET = "contract-clause-sheet-$ACCT"

aws s3api create-bucket --bucket $BUCKET --region $REGION
aws s3api put-public-access-block --bucket $BUCKET --public-access-block-configuration "BlockPublicAcls=false,IgnorePublicAcls=false,BlockPublicPolicy=false,RestrictPublicBuckets=false"
(Get-Content aws/bucket-policy.json) -replace 'BUCKET_NAME', $BUCKET | Set-Content aws/bucket-policy.local.json
aws s3api put-bucket-policy --bucket $BUCKET --policy file://aws/bucket-policy.local.json
aws s3 website "s3://$BUCKET/" --index-document index.html
aws s3 cp web/index.html "s3://$BUCKET/index.html" --content-type "text/html; charset=utf-8"

"http://$BUCKET.s3-website-$REGION.amazonaws.com/"
```

Outside `us-east-1`, `create-bucket` also needs
`--create-bucket-configuration LocationConstraint=$REGION`.

Open the page and paste the Function URL into the field at the top; it is kept in
that browser only. To bake it in instead, set `ENDPOINT` at the top of the
`<script>` block in `web/index.html` and upload again — then the field disappears.

An S3 website endpoint is plain HTTP. A browser on an HTTPS page will not call an
HTTPS Function URL from an HTTP page without complaint in some configurations; if
you want HTTPS end to end, put CloudFront in front of the bucket. For a demo you
open yourself, HTTP is enough.

## Updating

```powershell
python build_lambda.py
aws lambda update-function-code --function-name $FN --zip-file fileb://sheet-lambda.zip --region $REGION
aws s3 cp web/index.html "s3://$BUCKET/index.html" --content-type "text/html; charset=utf-8"
```

## Tearing it down

Run this when you are done looking at it. Nothing here bills much, but an
endpoint you have forgotten about is an endpoint you are not watching.

```powershell
aws lambda delete-function-url-config --function-name $FN --region $REGION
aws lambda delete-function --function-name $FN --region $REGION
# Deleting the function removes its resource policy with it. If you ever delete
# only the URL and keep the function, remove the statements by hand:
#   aws lambda remove-permission --function-name $FN --statement-id FunctionURLAllowPublicAccess
#   aws lambda remove-permission --function-name $FN --statement-id FunctionURLAllowInvoke
aws logs delete-log-group --log-group-name "/aws/lambda/$FN" --region $REGION
aws iam detach-role-policy --role-name "$FN-role" --policy-arn arn:aws:iam::aws:policy/service-role/AWSLambdaBasicExecutionRole
aws iam delete-role --role-name "$FN-role"
aws s3 rm "s3://$BUCKET" --recursive
aws s3api delete-bucket --bucket $BUCKET --region $REGION
```

The log group outlives the function and keeps billing for storage, so delete it
explicitly. That is the one piece people leave behind.

## What this costs

Lambda's always-free allowance is **1,000,000 requests and 400,000 GB-seconds per
month**, and it does not expire with the introductory period.

At 512 MB and a 100 ms worst case, one request costs 0.05 GB-seconds. The free
compute allowance covers about 8 million such requests, so the **request count is
what binds first, not the compute**. A demo nobody hammers does not approach
either.

S3 is the part that is not always-free: a 35 KB page is a rounding error in
storage, GET requests are $0.0004 per thousand, and the first 100 GB/month of
data transfer out is free across AWS. Realistically this is cents per month, paid
from the introductory credits while they last.

The number worth keeping in view is the one that is **not** here: no OpenSearch
Serverless collection, no provisioned index, no per-token inference. Those are the
line items that turn a personal demo into a monthly bill, and this architecture has
none of them because the product does not need them.

## What this does not change

The deployment does not touch the model, the thresholds or the measurements. The
sheet returned by the Function URL is identical, row for row, to
`sheet.sheet()` run locally — verified on all 101 held-out contracts. The numbers
on the page are still the ones `measure_sheet.py` prints: 571 of 748 rows, 76.3%.
