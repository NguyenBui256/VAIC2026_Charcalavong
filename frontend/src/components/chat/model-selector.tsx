import type { ChatProvider } from "../../lib/chatApi";

export default function ModelSelector({
  providers,
  providerId,
  modelName,
  disabled,
  onChange,
}: {
  providers: ChatProvider[];
  providerId: string | null;
  modelName: string | null;
  disabled: boolean;
  onChange: (providerId: string, modelName: string) => void;
}) {
  const value = providerId && modelName ? `${providerId}:${modelName}` : "";
  return (
    <select
      aria-label="Mô hình AI"
      value={value}
      disabled={disabled}
      onChange={(event) => {
        const [provider, ...model] = event.target.value.split(":");
        onChange(provider, model.join(":"));
      }}
      className="vaic-form-input"
      style={{ width: "auto", minWidth: 210, fontSize: 12 }}
    >
      {providers.flatMap((provider) =>
        provider.models.map((model) => (
          <option key={`${provider.id}:${model.name}`} value={`${provider.id}:${model.name}`}>
            {provider.label} · {model.name}
          </option>
        )),
      )}
    </select>
  );
}
