# Debugging 422 Error in n8n

## The Error
```
422 - "field required" for "audio_file"
```

This means the API isn't receiving the `audio_file` parameter correctly.

## Step-by-Step Debugging

### Step 1: Verify Parameter Name in n8n

In your HTTP Request node, check:
- **Parameter Name**: Must be exactly `audio_file` (not `file`, not `audio`)
- **Parameter Type**: Must be `File` (not `String`)
- **Parameter Value**: `={{ $binary.data }}` or `={{ $binary.audio }}`

### Step 2: Check What Your Webhook Receives

Add a **Function Node** right after your Webhook node:

```javascript
// Debug: See what binary data is available
return {
  json: {
    hasBinary: !!$input.first().binary,
    binaryKeys: Object.keys($input.first().binary || {}),
    firstBinaryKey: Object.keys($input.first().binary || {})[0],
    // Show structure
    binaryStructure: $input.first().binary
  }
};
```

This will show you what field name to use (might be `data`, `audio`, or something else).

### Step 3: Correct HTTP Request Configuration

**In HTTP Request Node:**

1. **Method**: `POST`
2. **URL**: `http://whisper-app-template.ai.svc.cluster.local:9000/asr`
3. **Body Content Type**: `Form-Data` or `Multipart-Form-Data`
4. **Parameters** (in "Specify Body"):
   
   ```
   Name: audio_file
   Type: File
   Value: ={{ $binary.data }}  (or whatever key you found in Step 2)
   
   Name: task
   Type: String
   Value: transcribe
   
   Name: language
   Type: String
   Value: en
   
   Name: response_format
   Type: String
   Value: json
   ```

### Step 4: Alternative - Use Code Node to Build Request

If the HTTP Request node continues to have issues, use a Code node:

```javascript
// Get binary data
const binaryData = $input.first().binary.data || $input.first().binary.audio;

if (!binaryData) {
  throw new Error('No binary data found. Available keys: ' + Object.keys($input.first().binary || {}));
}

// Return data for HTTP Request node
return {
  json: {
    url: 'http://whisper-app-template.ai.svc.cluster.local:9000/asr',
    method: 'POST',
    body: {
      audio_file: binaryData,
      task: 'transcribe',
      language: 'en',
      response_format: 'json'
    },
    options: {
      bodyContentType: 'multipart-form-data'
    }
  },
  binary: {
    audio_file: binaryData
  }
};
```

Then configure HTTP Request node to use the output from Code node.

### Step 5: Test with Direct cURL

Test the API directly to verify it works:

```bash
# From within the cluster (or port-forward)
curl -X POST "http://whisper-app-template.ai.svc.cluster.local:9000/asr" \
  -F "audio_file=@/tmp/test-whisper.wav" \
  -F "task=transcribe" \
  -F "language=en" \
  -F "response_format=json"
```

If this works, the issue is in how n8n is sending the data.

## Common Issues

1. **Wrong Parameter Name**: Using `file` instead of `audio_file`
2. **Wrong Type**: Parameter is `String` instead of `File`
3. **Binary Data Not Passed**: `$binary.data` doesn't exist - check webhook output
4. **Form-Data Not Selected**: Body Content Type is wrong

## Quick Fix Checklist

- [ ] Parameter name is exactly `audio_file` (case-sensitive)
- [ ] Parameter type is `File` (not String)
- [ ] Body Content Type is `Form-Data` or `Multipart-Form-Data`
- [ ] Binary data exists: Check with Function node after Webhook
- [ ] Using correct binary key: `$binary.data` or `$binary.audio` (check webhook output)

