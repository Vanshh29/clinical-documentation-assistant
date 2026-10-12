{{- define "cda.name" -}}
{{- default .Chart.Name .Values.nameOverride | trunc 63 | trimSuffix "-" -}}
{{- end -}}

{{- define "cda.fullname" -}}
{{- if .Values.fullnameOverride -}}
{{- .Values.fullnameOverride | trunc 63 | trimSuffix "-" -}}
{{- else -}}
{{- printf "%s-%s" .Release.Name (include "cda.name" .) | trunc 63 | trimSuffix "-" -}}
{{- end -}}
{{- end -}}

{{- define "cda.labels" -}}
helm.sh/chart: {{ printf "%s-%s" .Chart.Name .Chart.Version }}
app.kubernetes.io/name: {{ include "cda.name" . }}
app.kubernetes.io/instance: {{ .Release.Name }}
app.kubernetes.io/version: {{ .Chart.AppVersion | quote }}
app.kubernetes.io/managed-by: {{ .Release.Service }}
{{- end -}}

{{/* Selector labels. Call with (dict "root" . "component" "api"). */}}
{{- define "cda.selector" -}}
app.kubernetes.io/name: {{ include "cda.name" .root }}
app.kubernetes.io/instance: {{ .root.Release.Name }}
app.kubernetes.io/component: {{ .component }}
{{- end -}}

{{/* repository:tag, refusing empty or "latest" tags. Call with (dict "image" .Values.images.api "name" "api"). */}}
{{- define "cda.image" -}}
{{- $tag := required (printf "images.%s.tag is required" .name) .image.tag -}}
{{- if eq $tag "latest" -}}{{- fail (printf "images.%s.tag must not be 'latest'" .name) -}}{{- end -}}
{{- printf "%s:%s" .image.repository $tag -}}
{{- end -}}

{{- define "cda.secretName" -}}
{{- .Values.secrets.existingSecret -}}
{{- end -}}

{{- define "cda.serviceAccountName" -}}
{{- if .Values.serviceAccount.create -}}{{ include "cda.fullname" . }}{{- else -}}default{{- end -}}
{{- end -}}

{{/* Pod-level hardening. Call with (dict "uid" 10001). */}}
{{- define "cda.podSecurityContext" -}}
runAsNonRoot: true
runAsUser: {{ .uid }}
runAsGroup: {{ .uid }}
fsGroup: {{ .uid }}
seccompProfile:
  type: RuntimeDefault
{{- end -}}

{{- define "cda.containerSecurityContext" -}}
allowPrivilegeEscalation: false
readOnlyRootFilesystem: true
capabilities:
  drop: ["ALL"]
{{- end -}}

{{/* ConfigMap shared by every app container. */}}
{{- define "cda.appEnvFrom" -}}
- configMapRef:
    name: {{ include "cda.fullname" . }}-config
{{- end -}}

{{/* Secret-backed variables every app container needs (list items, no key). */}}
{{- define "cda.appEnvVars" -}}
- name: DATABASE_URL
  valueFrom: { secretKeyRef: { name: {{ include "cda.secretName" . }}, key: DATABASE_URL } }
- name: PII_ENCRYPTION_KEY
  valueFrom: { secretKeyRef: { name: {{ include "cda.secretName" . }}, key: PII_ENCRYPTION_KEY } }
- name: AUTH_JWT_SECRET
  valueFrom: { secretKeyRef: { name: {{ include "cda.secretName" . }}, key: AUTH_JWT_SECRET } }
{{- end -}}

{{/* Migrate inside each API pod when asked to, or when the database lives in this release. */}}
{{- define "cda.migrateInInit" -}}
{{- if and .Values.migrations.enabled (or (eq .Values.migrations.mode "initContainer") .Values.devInfra.postgres.enabled) -}}true{{- end -}}
{{- end -}}
