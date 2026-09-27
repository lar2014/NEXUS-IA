// Generado por Supabase (generate_typescript_types) a partir del esquema REAL
// ya aplicado en el proyecto nexus-cloud (ipdgezppzuwvrgzfwwpu). No editar a
// mano — si el esquema cambia, regenerar con la misma herramienta.

export type Json =
  | string
  | number
  | boolean
  | null
  | { [key: string]: Json | undefined }
  | Json[]

export type Database = {
  // Allows to automatically instantiate createClient with right options
  // instead of createClient<Database, { PostgrestVersion: 'XX' }>(URL, KEY)
  __InternalSupabase: {
    PostgrestVersion: "14.5"
  }
  public: {
    Tables: {
      actions_log: {
        Row: {
          action_type: string
          created_at: string
          device_id: string
          executed_at: string | null
          id: string
          params: Json
          result: string | null
          status: string
          target: string | null
          user_id: string
        }
        Insert: {
          action_type: string
          created_at?: string
          device_id: string
          executed_at?: string | null
          id?: string
          params?: Json
          result?: string | null
          status?: string
          target?: string | null
          user_id: string
        }
        Update: {
          action_type?: string
          created_at?: string
          device_id?: string
          executed_at?: string | null
          id?: string
          params?: Json
          result?: string | null
          status?: string
          target?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "actions_log_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      conversations: {
        Row: {
          device_id: string | null
          ended_at: string | null
          id: string
          started_at: string
          summary: string | null
          user_id: string
        }
        Insert: {
          device_id?: string | null
          ended_at?: string | null
          id?: string
          started_at?: string
          summary?: string | null
          user_id: string
        }
        Update: {
          device_id?: string | null
          ended_at?: string | null
          id?: string
          started_at?: string
          summary?: string | null
          user_id?: string
        }
        Relationships: [
          {
            foreignKeyName: "conversations_device_id_fkey"
            columns: ["device_id"]
            isOneToOne: false
            referencedRelation: "devices"
            referencedColumns: ["id"]
          },
        ]
      }
      devices: {
        Row: {
          capabilities: Json
          connected: boolean
          device_secret_hash: string | null
          id: string
          last_seen: string | null
          linked_at: string
          name: string
          pairing_code: string | null
          pairing_expires_at: string | null
          permissions: Json
          type: string
          user_id: string
        }
        Insert: {
          capabilities?: Json
          connected?: boolean
          device_secret_hash?: string | null
          id?: string
          last_seen?: string | null
          linked_at?: string
          name: string
          pairing_code?: string | null
          pairing_expires_at?: string | null
          permissions?: Json
          type: string
          user_id: string
        }
        Update: {
          capabilities?: Json
          connected?: boolean
          device_secret_hash?: string | null
          id?: string
          last_seen?: string | null
          linked_at?: string
          name?: string
          pairing_code?: string | null
          pairing_expires_at?: string | null
          permissions?: Json
          type?: string
          user_id?: string
        }
        Relationships: []
      }
      memory_entries: {
        Row: {
          category: string
          id: string
          key: string
          updated_at: string
          user_id: string
          value: string
        }
        Insert: {
          category: string
          id?: string
          key: string
          updated_at?: string
          user_id: string
          value: string
        }
        Update: {
          category?: string
          id?: string
          key?: string
          updated_at?: string
          user_id?: string
          value?: string
        }
        Relationships: []
      }
      provider_configs: {
        Row: {
          api_key_vault_id: string | null
          created_at: string
          id: string
          is_default: boolean
          label: string | null
          provider: string
          user_id: string
        }
        Insert: {
          api_key_vault_id?: string | null
          created_at?: string
          id?: string
          is_default?: boolean
          label?: string | null
          provider: string
          user_id: string
        }
        Update: {
          api_key_vault_id?: string | null
          created_at?: string
          id?: string
          is_default?: boolean
          label?: string | null
          provider?: string
          user_id?: string
        }
        Relationships: []
      }
    }
    Views: {
      [_ in never]: never
    }
    Functions: {
      create_provider_secret: {
        Args: { p_api_key: string; p_label: string; p_provider: string }
        Returns: string
      }
      get_provider_secret: { Args: { p_config_id: string }; Returns: string }
    }
    Enums: {
      [_ in never]: never
    }
    CompositeTypes: {
      [_ in never]: never
    }
  }
}

type DatabaseWithoutInternals = Omit<Database, "__InternalSupabase">

type DefaultSchema = DatabaseWithoutInternals[Extract<keyof Database, "public">]

export type Tables<
  DefaultSchemaTableNameOrOptions extends
    | keyof (DefaultSchema["Tables"] & DefaultSchema["Views"])
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
        DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? (DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"] &
      DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Views"])[TableName] extends {
      Row: infer R
    }
    ? R
    : never
  : DefaultSchemaTableNameOrOptions extends keyof (DefaultSchema["Tables"] &
        DefaultSchema["Views"])
    ? (DefaultSchema["Tables"] &
        DefaultSchema["Views"])[DefaultSchemaTableNameOrOptions] extends {
        Row: infer R
      }
      ? R
      : never
    : never

export type TablesInsert<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Insert: infer I
    }
    ? I
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Insert: infer I
      }
      ? I
      : never
    : never

export type TablesUpdate<
  DefaultSchemaTableNameOrOptions extends
    | keyof DefaultSchema["Tables"]
    | { schema: keyof DatabaseWithoutInternals },
  TableName extends (DefaultSchemaTableNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"]
    : never) = never,
> = DefaultSchemaTableNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaTableNameOrOptions["schema"]]["Tables"][TableName] extends {
      Update: infer U
    }
    ? U
    : never
  : DefaultSchemaTableNameOrOptions extends keyof DefaultSchema["Tables"]
    ? DefaultSchema["Tables"][DefaultSchemaTableNameOrOptions] extends {
        Update: infer U
      }
      ? U
      : never
    : never

export type Enums<
  DefaultSchemaEnumNameOrOptions extends
    | keyof DefaultSchema["Enums"]
    | { schema: keyof DatabaseWithoutInternals },
  EnumName extends (DefaultSchemaEnumNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"]
    : never) = never,
> = DefaultSchemaEnumNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[DefaultSchemaEnumNameOrOptions["schema"]]["Enums"][EnumName]
  : DefaultSchemaEnumNameOrOptions extends keyof DefaultSchema["Enums"]
    ? DefaultSchema["Enums"][DefaultSchemaEnumNameOrOptions]
    : never

export type CompositeTypes<
  PublicCompositeTypeNameOrOptions extends
    | keyof DefaultSchema["CompositeTypes"]
    | { schema: keyof DatabaseWithoutInternals },
  CompositeTypeName extends (PublicCompositeTypeNameOrOptions extends {
    schema: keyof DatabaseWithoutInternals
  }
    ? keyof DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"]
    : never) = never,
> = PublicCompositeTypeNameOrOptions extends {
  schema: keyof DatabaseWithoutInternals
}
  ? DatabaseWithoutInternals[PublicCompositeTypeNameOrOptions["schema"]]["CompositeTypes"][CompositeTypeName]
  : PublicCompositeTypeNameOrOptions extends keyof DefaultSchema["CompositeTypes"]
    ? DefaultSchema["CompositeTypes"][PublicCompositeTypeNameOrOptions]
    : never

export const Constants = {
  public: {
    Enums: {},
  },
} as const
