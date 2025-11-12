# n8n HTTP Request Node - File Upload Troubleshooting

## Common Error: "Cannot read properties of undefined (reading 'id')"

This error occurs when the file parameter in the HTTP Request node isn't properly configured for binary data.

## Solution: Proper File Upload Configuration

### Step-by-Step Fix:

1. **In your HTTP Request node:**
   - **Method**: `POST`
   - **URL**: `http://whisper-app-template.ai.svc.cluster.local:9000/asr`
   - **Body Content Type**: Select `"Form-Data"` or `"Multipart-Form-Data"`

2. **In the "Specify Body" section:**
   - Click **"Add Parameter"** or **"Add Field"**
   - For the **file parameter**:
     - **Name**: `audio_file` (important: the API expects `audio_file`, not `file`)
     - **Type**: Select **"File"** (not "String" or "Number")
     - **Value**: `={{ $binary.data }}` or `={{ $binary.audio }}` (depending on your webhook field name)

3. **Add other parameters as String type:**
   - **Name**: `task`, **Type**: String, **Value**: `transcribe`
   - **Name**: `language`, **Type**: String, **Value**: `en`
   - **Name**: `response_format`, **Type**: String, **Value**: `json`

## Alternative: Use "Specify Binary Data" Option

If the form-data approach doesn't work:

1. **Body Content Type**: Select `"Raw"` or `"Binary"`

2. **Use "Specify Binary Data"**:
   - Set to: `={{ $binary.data }}` or `={{ $binary.audio }}`

3. **Add headers**:
   - `Content-Type`: `multipart/form-data`

## Check Your Webhook Node

Make sure your Webhook node is configured to:
- **HTTP Method**: `POST`
- **Response Mode**: `Last Node` or `When Last Node Finishes`
- **Binary Data**: Enabled/Checked

## Debugging Steps

1. **Check what the webhook receives:**
   Add a **Function Node** after the Webhook:
   ```javascript
   return {
     json: {
       binaryKeys: Object.keys($input.first().binary || {}),
       hasBinary: !!$input.first().binary
     }
   };
   ```

2. **Check binary data structure:**
   ```javascript
   return {
     json: {
       binaryData: $input.first().binary?.data || $input.first().binary?.audio,
       mimeType: $input.first().binary?.data?.mimeType || $input.first().binary?.audio?.mimeType
     }
   };
   ```

## Correct Parameter Configuration

### Option 1: Form-Data with File Type
```
Body Content Type: Form-Data

Parameters:
┌────────────┬──────────┬──────────────────────┐
│ Name       │ Type     │ Value                │
├────────────┼──────────┼──────────────────────┤
│ audio_file │ File     │ {{ $binary.data }}   │
│ task       │ String   │ transcribe           │
│ language   │ String   │ en                    │
│ response_  │ String   │ json                 │
│ format     │          │                      │
└────────────┴──────────┴──────────────────────┘
```

### Option 2: Using Binary Data Directly
If form-data doesn't work, you might need to construct the multipart form manually or use a different approach.

## Alternative: Use Code Node to Build Request

If the HTTP Request node continues to have issues, use a **Code Node** to build the request:

```javascript
const FormData = require('form-data');
const fs = require('fs');

// Get binary data from previous node
const binaryData = $input.first().binary.data || $input.first().binary.audio;

// Create form data
const form = new FormData();
form.append('file', Buffer.from(binaryData.data, 'base64'), {
  filename: binaryData.fileName || 'audio.wav',
  contentType: binaryData.mimeType || 'audio/wav'
});
form.append('task', 'transcribe');
form.append('language', 'en');
form.append('response_format', 'json');

return {
  json: {
    formData: form,
    headers: form.getHeaders()
  }
};
```

Then use HTTP Request node with the output from Code node.

## Quick Fix Checklist

- [ ] Body Content Type is set to "Form-Data" or "Multipart-Form-Data"
- [ ] File parameter **Name** is `audio_file` (not `file`)
- [ ] File parameter Type is set to "File" (not "String")
- [ ] File parameter Value uses `={{ $binary.data }}` or `={{ $binary.audio }}`
- [ ] Webhook node has Binary Data enabled
- [ ] Other parameters (task, language, etc.) are String type

## Still Not Working?

Try this simplified test:
1. Remove all parameters except `file`
2. Set file parameter correctly as File type
3. Test with just the file upload
4. Add other parameters one by one

